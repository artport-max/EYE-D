"""VIP / 단골(regular) / 재방문(returning) / 신규(new) 자동 분류 서비스.

설계 원칙
---------
- 매칭(matcher.find_or_create_global_id) 결과를 받아 호출.
- DB 정합성은 PostgreSQL 트랜잭션에 위임(이 모듈은 SQL 한 번에 처리).
- 한 사람의 "방문"은 person_visits 레코드 1개로 묶고, visit_count = person_visits 행 수.
- VIP는 운영자가 수동 지정한 사람만 True (자동 승격 없음, 오탐 위험 회피).
- regular(단골)는 visit_count >= REGULAR_VISIT_THRESHOLD 가 되면 자동 승격.

분류 규칙 (우선순위 위→아래)
---------------------------
1) is_vip = TRUE                         → 'vip'
2) visit_count >= REGULAR_VISIT_THRESHOLD → 'regular'
3) visit_count >= 2                       → 'returning'
4) 그 외                                  → 'new'

호출 시점
---------
- security.post_detection 안에서 매칭 직후, 같은 트랜잭션(conn) 으로 호출.
- 새로운 person_visits 행을 만들지(=새 방문 시작) 아니면 기존 visit 의 ended_at 만 늘릴지는
  upsert_person_visit() 가 결정한다 (REVISIT_GAP_SECONDS 기준).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

import asyncpg


# ---------- 설정 ----------
def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


REGULAR_VISIT_THRESHOLD = _int_env("REGULAR_VISIT_THRESHOLD", 5)
REVISIT_GAP_SECONDS = _int_env("REVISIT_GAP_SECONDS", 900)  # 15분


# ---------- 반환 타입 ----------
@dataclass
class ClassificationResult:
    global_id: int
    visit_count: int
    customer_tier: str           # 'new' | 'returning' | 'regular' | 'vip'
    is_vip: bool
    tier_changed: bool           # 이번 호출로 tier 가 바뀌었는지
    new_visit_started: bool      # 이번 호출로 새로운 방문이 시작됐는지


# ---------- 메인 진입점 ----------
async def classify_and_record(
    conn: asyncpg.Connection,
    global_id: int,
    detected_at: datetime,
    is_intrusion: bool,
    primary_camera: str | None = None,
) -> ClassificationResult:
    """매칭된 사람 1명에 대해 방문 갱신 + 등급 재산정.

    - REVISIT_GAP_SECONDS 안에 같은 사람이 다시 잡히면 같은 방문으로 본다.
    - 그보다 오래 비어 있으면 새 방문을 시작한다 (visit_count + 1).
    """
    # 1) 현재 사람의 상태 조회 (없으면 새 행이 이미 있어야 함 — 매칭 단계 책임)
    person = await conn.fetchrow(
        """
        SELECT global_id, is_vip, customer_tier, visit_count, last_visit_at
        FROM persons WHERE global_id = $1
        """,
        global_id,
    )
    if person is None:
        raise ValueError(f"person not found: global_id={global_id}")

    prev_tier = person["customer_tier"]
    is_vip = bool(person["is_vip"])
    visit_count = int(person["visit_count"])
    last_visit_at = person["last_visit_at"]

    # 2) 새 방문이냐, 같은 방문 연장이냐 결정
    new_visit_started = False
    if last_visit_at is None:
        new_visit_started = True
    else:
        gap = (detected_at - last_visit_at).total_seconds()
        if gap > REVISIT_GAP_SECONDS:
            new_visit_started = True

    if new_visit_started:
        visit_count += 1
        await conn.execute(
            """
            INSERT INTO person_visits
                (global_id, started_at, ended_at, detection_count,
                 primary_camera, is_intrusion)
            VALUES ($1, $2, $2, 1, $3, $4)
            """,
            global_id, detected_at, primary_camera, is_intrusion,
        )
    else:
        # 같은 방문 — 가장 최근 visit 의 ended_at / detection_count 갱신
        await conn.execute(
            """
            UPDATE person_visits SET
                ended_at        = GREATEST(ended_at, $2),
                detection_count = detection_count + 1,
                is_intrusion    = (is_intrusion OR $3::boolean)
            WHERE visit_id = (
                SELECT visit_id FROM person_visits
                WHERE global_id = $1
                ORDER BY started_at DESC
                LIMIT 1
            )
            """,
            global_id, detected_at, is_intrusion,
        )

    # 3) 새 tier 산정
    new_tier = _decide_tier(is_vip=is_vip, visit_count=visit_count)
    tier_changed = new_tier != prev_tier

    # 4) persons 갱신 (visit_count, customer_tier, last_visit_at)
    await conn.execute(
        """
        UPDATE persons SET
            visit_count   = $2,
            customer_tier = $3,
            last_visit_at = $4
        WHERE global_id = $1
        """,
        global_id, visit_count, new_tier, detected_at,
    )

    return ClassificationResult(
        global_id=global_id,
        visit_count=visit_count,
        customer_tier=new_tier,
        is_vip=is_vip,
        tier_changed=tier_changed,
        new_visit_started=new_visit_started,
    )


# ---------- 분류 규칙 ----------
def _decide_tier(*, is_vip: bool, visit_count: int) -> str:
    if is_vip:
        return "vip"
    if visit_count >= REGULAR_VISIT_THRESHOLD:
        return "regular"
    if visit_count >= 2:
        return "returning"
    return "new"


# ---------- 운영자용 ----------
async def set_vip(conn: asyncpg.Connection, global_id: int,
                  is_vip: bool = True, display_name: str | None = None) -> None:
    """운영자가 특정 사람을 VIP 로 지정/해제."""
    new_tier_sql = "CASE WHEN $2 THEN 'vip' "\
                   f"WHEN visit_count >= {REGULAR_VISIT_THRESHOLD} THEN 'regular' "\
                   "WHEN visit_count >= 2 THEN 'returning' ELSE 'new' END"
    await conn.execute(
        f"""
        UPDATE persons SET
            is_vip = $2,
            display_name = COALESCE($3, display_name),
            customer_tier = {new_tier_sql}
        WHERE global_id = $1
        """,
        global_id, is_vip, display_name,
    )
