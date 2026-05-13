"""엣지를 흉내내 가짜 페이로드를 백엔드에 송신.
팀장님 OSNet 완성 전 백엔드 단독 검증/시연용.

실행: python tools/mock_sender.py
"""
import asyncio
import random
from datetime import datetime, timezone
import httpx

API = "http://127.0.0.1:8000/api/v1/security/detections"
EMBEDDING_DIM = 512


def fake_embedding(seed: int) -> list[float]:
    """같은 seed면 같은 벡터를 만든다 (같은 사람 흉내).
    seed가 다르면 완전히 다른 벡터 → 다른 사람."""
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]


async def send_one(client: httpx.AsyncClient, person_seed: int, cam: str):
    payload = {
        "camera_id": cam,
        "tracklet_id": f"T_{random.randint(1000, 9999)}",
        "embedding_identity": fake_embedding(person_seed),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bbox": [10, 20, 100, 200],
        # 1/3 확률로 intrusion → WebSocket 알림 발동
        "event_type": random.choice(["detection", "detection", "intrusion"]),
    }
    r = await client.post(API, json=payload, timeout=5.0)
    data = r.json()
    print(f"[{r.status_code}] person_seed={person_seed} cam={cam} "
          f"event={payload['event_type']:9s} "
          f"→ det_id={data.get('detection_id')} "
          f"global_id={data.get('global_id')} matched={data.get('matched')}")


async def main():
    async with httpx.AsyncClient() as client:
        # 5명을 각각 3번씩 등장시킴 → 15건 송신
        # 같은 person_seed 끼리는 동일 global_id로 묶여야 정상
        for round_ in range(3):
            print(f"\n--- Round {round_ + 1}/3 ---")
            for person in range(5):
                cam = random.choice(["CAM_01"])  # 카메라 추가 시 리스트 확장
                await send_one(client, person_seed=person, cam=cam)
                await asyncio.sleep(0.2)  # 너무 빨라서 로그 따라가기 힘들면 늘리기


if __name__ == "__main__":
    asyncio.run(main())