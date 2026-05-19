"""Smart Retail 라우터 — VIP/단골 관리 + 체류·동선 통계.

prefix: /api/v1/retail
의존: app.db.conn, app.services.customer_classifier, app.services.dwell_analyzer

엔드포인트 한 줄 요약
---------------------
POST   /persons/{global_id}/vip          VIP 지정/해제 (운영자)
GET    /vips                              VIP 목록
GET    /persons                           등급별 인물 목록 (tier 필터 가능)
GET    /persons/{global_id}/stats         특정 인물 통계 (체류/동선/시간대)
GET    /stats/hourly                      시간대별 혼잡도
GET    /stats/zones                       zone 별 체류 요약
GET    /stats/duration                    체류시간 분포
"""
from __future__ import annotations

from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.conn import get_pool
from app.services import customer_classifier, dwell_analyzer


router = APIRouter(prefix="/api/v1/retail", tags=["retail"])


# ---------- Pydantic 입력 ----------
class VipUpdateIn(BaseModel):
    is_vip: bool = True
    display_name: Optional[str] = None


# ============================================================
# 1) VIP 운영
# ============================================================
@router.post("/persons/{global_id}/vip")
async def set_vip(global_id: int, payload: VipUpdateIn):
    """운영자가 특정 사람을 VIP 로 지정/해제."""
    pool = get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM persons WHERE global_id = $1", global_id
        )
        if not exists:
            raise HTTPException(404, f"person not found: {global_id}")
        await customer_classifier.set_vip(
            conn, global_id, payload.is_vip, payload.display_name
        )
        row = await conn.fetchrow(
            "SELECT global_id, is_vip, customer_tier, display_name "
            "FROM persons WHERE global_id = $1",
            global_id,
        )
    return dict(row)


@router.get("/vips")
async def list_vips(limit: int = Query(default=200, le=1000)):
    """VIP 로 지정된 인물 목록 + 방문 통계."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT global_id, display_name, customer_tier,
                   visit_count, last_visit_at, first_seen_at, notes
            FROM persons
            WHERE is_vip = TRUE
            ORDER BY last_visit_at DESC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


# ============================================================
# 2) 등급별 인물 목록
# ============================================================
Tier = Literal["new", "returning", "regular", "vip"]


@router.get("/persons")
async def list_persons_by_tier(
    tier: Optional[Tier] = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        if tier is None:
            rows = await conn.fetch(
                """
                SELECT global_id, customer_tier, is_vip, visit_count,
                       last_visit_at, display_name
                FROM persons
                ORDER BY last_visit_at DESC NULLS LAST
                LIMIT $1
                """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT global_id, customer_tier, is_vip, visit_count,
                       last_visit_at, display_name
                FROM persons
                WHERE customer_tier = $1
                ORDER BY last_visit_at DESC NULLS LAST
                LIMIT $2
                """,
                tier, limit,
            )
    return [dict(r) for r in rows]


# ============================================================
# 3) 특징 분석 — 인물별
# ============================================================
@router.get("/persons/{global_id}/stats")
async def person_stats(
    global_id: int,
    days: int = Query(default=30, ge=1, le=365),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM persons WHERE global_id = $1", global_id
        )
        if not exists:
            raise HTTPException(404, f"person not found: {global_id}")
        return await dwell_analyzer.person_stats(conn, global_id, days=days)


# ============================================================
# 4) 특징 분석 — 전체 집계
# ============================================================
@router.get("/stats/hourly")
async def stats_hourly(days: int = Query(default=7, ge=1, le=90)):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await dwell_analyzer.hourly_traffic(conn, days=days)


@router.get("/stats/zones")
async def stats_zones(days: int = Query(default=7, ge=1, le=90)):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await dwell_analyzer.zone_summary(conn, days=days)


@router.get("/stats/duration")
async def stats_duration(days: int = Query(default=7, ge=1, le=90)):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await dwell_analyzer.visit_duration_distribution(conn, days=days)
