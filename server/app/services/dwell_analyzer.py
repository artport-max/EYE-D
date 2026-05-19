"""체류(dwell) · 동선(zone trajectory) 특징 분석 서비스.

설계 원칙
---------
- 모든 집계 쿼리는 person_visits / zone_visits 위에서만 돈다.
  ┗ detections 테이블(=raw event)을 매번 스캔하지 않게 해 인덱스 안정성 확보.
- 같은 함수 한 벌로 (a) 한 사람 통계, (b) 전체 집계 둘 다 지원.
- 결과는 모두 dict (JSON 직렬화 가능) — 라우터에서 그대로 반환 가능.

용도
----
- Smart Retail 대시보드: VIP/단골 카드의 "지난 방문 평균 18분 · 보통 17~19시" 같은 라인
- arttrace 확장 시: 관람객의 zone 시퀀스를 그대로 mood_vector 입력으로 넘김
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import asyncpg


# ============================================================
# 1) 한 사람(인물) 단위 — 카드 디테일 / 시간대 / 동선
# ============================================================
async def person_stats(
    conn: asyncpg.Connection,
    global_id: int,
    days: int = 30,
) -> dict:
    """특정 사람의 최근 N일 통계."""
    since = datetime.utcnow() - timedelta(days=days)

    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                                          AS visit_count,
            COALESCE(AVG(duration_sec), 0)                    AS avg_duration_sec,
            COALESCE(MAX(duration_sec), 0)                    AS max_duration_sec,
            COALESCE(SUM(duration_sec), 0)                    AS total_duration_sec,
            MIN(started_at)                                   AS first_visit_at,
            MAX(started_at)                                   AS last_visit_at,
            COUNT(*) FILTER (WHERE is_intrusion)              AS intrusion_count
        FROM person_visits
        WHERE global_id = $1 AND started_at >= $2
        """,
        global_id, since,
    )

    # 시간대별 방문 분포 (0~23시 버킷)
    hour_rows = await conn.fetch(
        """
        SELECT EXTRACT(HOUR FROM started_at)::INT AS hour,
               COUNT(*) AS cnt
        FROM person_visits
        WHERE global_id = $1 AND started_at >= $2
        GROUP BY 1 ORDER BY 1
        """,
        global_id, since,
    )
    hour_dist = {int(r["hour"]): int(r["cnt"]) for r in hour_rows}

    # 동선: 최근 1회 방문의 zone sequence
    seq_rows = await conn.fetch(
        """
        SELECT zv.zone_id, z.name, zv.entered_at, zv.exited_at, zv.dwell_sec
        FROM zone_visits zv
        JOIN zones z ON z.zone_id = zv.zone_id
        WHERE zv.global_id = $1
        ORDER BY zv.entered_at DESC
        LIMIT 50
        """,
        global_id,
    )
    last_trajectory = [
        {
            "zone_id": r["zone_id"],
            "zone_name": r["name"],
            "entered_at": r["entered_at"].isoformat() if r["entered_at"] else None,
            "exited_at":  r["exited_at"].isoformat()  if r["exited_at"]  else None,
            "dwell_sec":  float(r["dwell_sec"]) if r["dwell_sec"] is not None else 0.0,
        }
        for r in seq_rows
    ]

    return {
        "global_id": global_id,
        "window_days": days,
        "visit_count":         int(row["visit_count"] or 0),
        "avg_duration_sec":    float(row["avg_duration_sec"] or 0),
        "max_duration_sec":    float(row["max_duration_sec"] or 0),
        "total_duration_sec":  float(row["total_duration_sec"] or 0),
        "first_visit_at":      row["first_visit_at"].isoformat() if row["first_visit_at"] else None,
        "last_visit_at":       row["last_visit_at"].isoformat()  if row["last_visit_at"]  else None,
        "intrusion_count":     int(row["intrusion_count"] or 0),
        "hour_distribution":   hour_dist,
        "recent_trajectory":   last_trajectory,
    }


# ============================================================
# 2) 전체 집계 — 운영 대시보드용
# ============================================================
async def hourly_traffic(
    conn: asyncpg.Connection,
    days: int = 7,
) -> list[dict]:
    """최근 N일 시간대별 방문 인원 (혼잡도 곡선용)."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = await conn.fetch(
        """
        SELECT EXTRACT(HOUR FROM started_at)::INT AS hour,
               COUNT(*) AS visits,
               COUNT(DISTINCT global_id) AS unique_visitors,
               COALESCE(AVG(duration_sec), 0) AS avg_duration_sec
        FROM person_visits
        WHERE started_at >= $1
        GROUP BY 1 ORDER BY 1
        """,
        since,
    )
    return [
        {
            "hour": int(r["hour"]),
            "visits": int(r["visits"]),
            "unique_visitors": int(r["unique_visitors"]),
            "avg_duration_sec": float(r["avg_duration_sec"]),
        }
        for r in rows
    ]


async def zone_summary(
    conn: asyncpg.Connection,
    days: int = 7,
) -> list[dict]:
    """zone 별 평균 체류·방문 수 — '가장 오래 머무는 구역' 확인."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = await conn.fetch(
        """
        SELECT z.zone_id, z.name, z.purpose,
               COUNT(zv.zone_visit_id) AS visit_count,
               COUNT(DISTINCT zv.global_id) AS unique_visitors,
               COALESCE(AVG(zv.dwell_sec), 0) AS avg_dwell_sec,
               COALESCE(MAX(zv.dwell_sec), 0) AS max_dwell_sec
        FROM zones z
        LEFT JOIN zone_visits zv
          ON zv.zone_id = z.zone_id AND zv.entered_at >= $1
        GROUP BY z.zone_id, z.name, z.purpose
        ORDER BY visit_count DESC
        """,
        since,
    )
    return [
        {
            "zone_id":         r["zone_id"],
            "zone_name":       r["name"],
            "purpose":         r["purpose"],
            "visit_count":     int(r["visit_count"]),
            "unique_visitors": int(r["unique_visitors"]),
            "avg_dwell_sec":   float(r["avg_dwell_sec"]),
            "max_dwell_sec":   float(r["max_dwell_sec"]),
        }
        for r in rows
    ]


async def visit_duration_distribution(
    conn: asyncpg.Connection,
    days: int = 7,
    buckets_sec: Optional[list[int]] = None,
) -> list[dict]:
    """체류시간 분포 (히스토그램). 기본 버킷: 1분/5분/15분/30분/1h/2h+."""
    since = datetime.utcnow() - timedelta(days=days)
    if buckets_sec is None:
        buckets_sec = [60, 300, 900, 1800, 3600, 7200]
    # WIDTH_BUCKET 이용한 히스토그램
    rows = await conn.fetch(
        f"""
        WITH src AS (
            SELECT duration_sec FROM person_visits WHERE started_at >= $1
        )
        SELECT WIDTH_BUCKET(duration_sec,
               ARRAY[{','.join(str(b) for b in buckets_sec)}]::REAL[]) AS bucket_idx,
               COUNT(*) AS cnt
        FROM src GROUP BY 1 ORDER BY 1
        """,
        since,
    )
    labels = (["<1m", "1-5m", "5-15m", "15-30m", "30m-1h", "1-2h"]
              + [f"{buckets_sec[-1]//3600}h+"])
    return [
        {"bucket": labels[int(r["bucket_idx"])] if int(r["bucket_idx"]) < len(labels) else "other",
         "count": int(r["cnt"])}
        for r in rows
    ]
