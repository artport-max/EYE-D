"""엣지를 흉내내 가짜 페이로드를 백엔드에 송신.
팀장님 OSNet 완성 전 백엔드 단독 검증/시연용.

2026-05-19 보강:
- 같은 사람을 REGULAR_VISIT_THRESHOLD(=기본 5) 이상 보내 단골 자동 승격 데모
- 매 라운드마다 시간을 REVISIT_GAP_SECONDS 이상 띄워 새로운 visit 로 인식되게 함
- 마지막에 GET /api/v1/retail/vips, /persons, /stats/hourly 호출해 결과 요약 출력

실행:
    .\.venv\Scripts\Activate.ps1
    python tools/mock_sender.py
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

import httpx

BASE   = "http://127.0.0.1:8000"
API_DET = f"{BASE}/api/v1/security/detections"
API_VIP = f"{BASE}/api/v1/retail/vips"
API_PER = f"{BASE}/api/v1/retail/persons"
API_HRS = f"{BASE}/api/v1/retail/stats/hourly"

EMBEDDING_DIM = 512
NUM_PEOPLE    = 5      # 사람 수 (각자 다른 seed)
NUM_ROUNDS    = 6      # 라운드 — 5번째 라운드부터 regular 승격 발생 (임계값 기본 5)
GAP_MINUTES   = 20     # 라운드 간 가상 시간 간격(분). REVISIT_GAP_SECONDS(=15분) 이상이어야 새 visit 로 인식.


def fake_embedding(seed: int) -> list[float]:
    """같은 seed면 같은 벡터(=같은 사람)."""
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]


async def send_one(client: httpx.AsyncClient,
                   person_seed: int, cam: str, ts: datetime, event_type: str):
    payload = {
        "camera_id": cam,
        "tracklet_id": f"T_{random.randint(1000, 9999)}",
        "embedding_identity": fake_embedding(person_seed),
        "timestamp": ts.isoformat(),
        "bbox": [10, 20, 100, 200],
        "event_type": event_type,
    }
    r = await client.post(API_DET, json=payload, timeout=5.0)
    data = r.json()
    print(f"  person={person_seed} cam={cam} event={event_type:9s} "
          f"→ det_id={data.get('detection_id')} "
          f"gid={data.get('global_id')} matched={data.get('matched')}")
    return data


async def summarize(client: httpx.AsyncClient):
    print("\n=== 결과 요약 ===")
    for label, url in [("VIP 목록", API_VIP), ("전체 인물(상위20)", f"{API_PER}?limit=20"),
                       ("시간대별 트래픽(7일)", f"{API_HRS}?days=7")]:
        r = await client.get(url, timeout=5.0)
        print(f"\n[{label}] {r.status_code}")
        body = r.json()
        if isinstance(body, list):
            for item in body[:20]:
                print(" ", item)
        else:
            print(body)


async def main():
    async with httpx.AsyncClient() as client:
        now = datetime.now(timezone.utc)
        for r in range(NUM_ROUNDS):
            # 각 라운드는 GAP_MINUTES 분만큼 가상 시간을 거슬러 올라간 시각으로 보낸다.
            # (라운드가 진행될수록 ts 는 최근쪽으로 옴 → 시간 순서대로 visit 누적)
            ts = now - timedelta(minutes=GAP_MINUTES * (NUM_ROUNDS - 1 - r))
            print(f"\n--- Round {r + 1}/{NUM_ROUNDS}  ts≈{ts.strftime('%H:%M:%S')} ---")
            for person in range(NUM_PEOPLE):
                # 1/6 확률로 intrusion 끼워 넣기 (보안 알림 분기도 동작 확인)
                event_type = random.choices(
                    ["detection", "intrusion"], weights=[5, 1]
                )[0]
                await send_one(client, person_seed=person, cam="CAM_01",
                               ts=ts, event_type=event_type)
                await asyncio.sleep(0.05)

        await summarize(client)
        print("\n→ 단골 승격(regular_visit) WebSocket 알림은 라운드 5 부근에 발생합니다.")
        print("→ /api/v1/retail/persons?tier=regular  로도 확인 가능합니다.")


if __name__ == "__main__":
    asyncio.run(main())
