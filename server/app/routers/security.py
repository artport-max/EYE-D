"""EYE-D 보안 라우터 — PS Center 본 도메인.
탐지 수신, 인물 동선 조회, 실시간 알림 WebSocket."""
import json
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.schemas.detection import DetectionIn, DetectionOut
from app.db.conn import get_pool
from app.services.matcher import find_or_create_global_id

router = APIRouter(prefix="/api/v1/security", tags=["security"])

# WebSocket 알림 구독자 목록 (보안 도메인 내부 상태)
_alert_clients: list[WebSocket] = []


async def broadcast_intrusion(detection_id: int, global_id: int, camera_id: str):
    """침입 이벤트를 연결된 모든 알림 클라이언트에 푸시."""
    msg = {
        "type": "intrusion",
        "detection_id": detection_id,
        "global_id": global_id,
        "camera_id": camera_id,
    }
    dead = []
    for c in _alert_clients:
        try:
            await c.send_json(msg)
        except Exception:
            dead.append(c)
    for d in dead:
        if d in _alert_clients:
            _alert_clients.remove(d)


@router.post("/detections", response_model=DetectionOut)
async def post_detection(payload: DetectionIn) -> DetectionOut:
    """엣지에서 탐지 이벤트를 받아 매칭 + DB 저장."""
    pool = get_pool()
    emb_str = "[" + ",".join(f"{x:.6f}" for x in payload.embedding_identity) + "]"

    async with pool.acquire() as conn:
        async with conn.transaction():
            global_id, sim, matched = await find_or_create_global_id(conn, emb_str)
            row = await conn.fetchrow(
                """
                INSERT INTO detections
                  (camera_id, tracklet_id, global_id, embedding_identity,
                   bbox, detected_at, is_intrusion,
                   pose_keypoints, action_label, dwell_seconds,
                   appearance_attrs, scene_context)
                VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING detection_id
                """,
                payload.camera_id, payload.tracklet_id, global_id,
                emb_str, json.dumps(payload.bbox), payload.timestamp,
                payload.event_type == "intrusion",
                json.dumps(payload.pose_keypoints) if payload.pose_keypoints else None,
                payload.action_label,
                payload.dwell_seconds,
                json.dumps(payload.appearance_attrs) if payload.appearance_attrs else None,
                json.dumps(payload.scene_context) if payload.scene_context else None,
            )
            await conn.execute(
                "UPDATE persons SET last_seen_at = $1 WHERE global_id = $2",
                payload.timestamp, global_id,
            )

    if payload.event_type == "intrusion":
        await broadcast_intrusion(
            detection_id=row["detection_id"],
            global_id=global_id,
            camera_id=payload.camera_id,
        )

    print(f"[DETECTION] saved id={row['detection_id']} global_id={global_id} "
          f"matched={matched} sim={sim}")

    return DetectionOut(
        detection_id=row["detection_id"],
        global_id=global_id,
        matched=matched,
        similarity=sim,
    )


@router.get("/persons/{global_id}/track")
async def get_person_track(
    global_id: int,
    limit: int = Query(default=100, le=1000, description="최대 반환 개수"),
):
    """특정 인물의 탐지 이력(동선)을 시간순으로 반환."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT detection_id, camera_id, detected_at, bbox, is_intrusion
            FROM detections
            WHERE global_id = $1
            ORDER BY detected_at ASC
            LIMIT $2
            """,
            global_id, limit,
        )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No detections for global_id={global_id}",
        )
    return [dict(r) for r in rows]


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    """알림 구독 채널. (전체 경로: /api/v1/security/ws/alerts)"""
    await ws.accept()
    _alert_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _alert_clients:
            _alert_clients.remove(ws)


@router.get("/stats/today")
async def get_today_stats():
    """오늘 탐지/침입 건수 + 현재 추적 인원."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE detected_at >= CURRENT_DATE) AS today_count,
                COUNT(*) FILTER (WHERE detected_at >= CURRENT_DATE
                                 AND is_intrusion = TRUE) AS today_intrusions,
                COUNT(DISTINCT global_id) FILTER (
                    WHERE detected_at > NOW() - INTERVAL '5 minutes'
                ) AS active_now
            FROM detections
        """)
    return dict(row)


@router.get("/detections/recent")
async def get_recent_detections(limit: int = Query(default=50, le=200)):
    """이벤트 타임라인용 최근 detection 목록."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT detection_id, camera_id, global_id, detected_at,
                   is_intrusion, tracklet_id
            FROM detections
            ORDER BY detected_at DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]            


@router.get("/persons")
async def list_persons(limit: int = Query(default=100, le=500)):
    """등록 인물 카드 그리드용 — 인물별 요약."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.global_id,
                p.first_seen_at,
                p.last_seen_at,
                COUNT(d.detection_id) AS detection_count,
                BOOL_OR(d.is_intrusion) AS has_intrusion,
                MAX(d.camera_id) AS last_camera
            FROM persons p
            LEFT JOIN detections d ON d.global_id = p.global_id
            GROUP BY p.global_id
            ORDER BY p.last_seen_at DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]