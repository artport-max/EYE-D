# 엣지 → 백엔드 페이로드 계약 (Contract)

대상: **엣지 파이프라인 담당(팀장)** 께 인계용 한 페이지 문서
작성: 2026-05-19 / 백엔드 담당
관련 코드: `app/schemas/detection.py`, `app/routers/security.py`

---

## 0. 한눈에

- **수신 URL**: `POST http://<백엔드호스트>:8000/api/v1/security/detections`
- **콘텐츠 타입**: `application/json`
- **인증**: 없음(연구 단계). 운영 전환 시 추가 예정.
- **응답**: `200 OK` + `{detection_id, global_id, matched, similarity}`
- **재시도**: 백엔드는 멱등성 보장 안 함 — 같은 detection 을 두 번 보내면 두 행 저장됨. 엣지에서 재시도 정책 결정.

## 1. 필수 필드 (DetectionIn)

| 필드 | 타입 | 예시 | 비고 |
|---|---|---|---|
| `camera_id` | string | `"CAM_01"` | `cameras` 테이블에 존재해야 함 (없으면 미리 INSERT 또는 백엔드에 사전 등록 요청) |
| `tracklet_id` | string | `"T_3142"` | 엣지 내부 임시 ID. 백엔드는 저장만 함 |
| `embedding_identity` | float[] | `[0.12, -0.04, ...]` (길이 512) | **OSNet 임베딩**. 차원은 아래 §3 참고 |
| `timestamp` | string(ISO8601) | `"2026-05-19T13:42:17.531+00:00"` | **UTC 권장**. 한국시간(`+09:00`)도 OK |
| `bbox` | float[4] | `[x1, y1, x2, y2]` | 픽셀 좌표 (절대값). 원본 프레임 기준 |
| `event_type` | string | `"detection"` 또는 `"intrusion"` | `"intrusion"` 이면 WebSocket 침입 알림 발화 |

## 2. 옵션 필드 (arttrace 확장 슬롯)

당장 안 보내도 됨. 차후 Phase B 에서 채울 자리.

| 필드 | 타입 | 비고 |
|---|---|---|
| `pose_keypoints` | float[][] | COCO 17-keypoint 등 |
| `action_label` | string | `"walking"`, `"standing"` 등 |
| `dwell_seconds` | float | 엣지에서 추정한 체류시간 |
| `appearance_attrs` | object | `{"color_top":"red", "gender":"f"}` 등 |
| `scene_context` | object | `{"crowd_level":0.3}` 등 |

## 3. 임베딩 차원 — **합의 필요**

현재 백엔드는 **512차원 고정** (`pgvector(512)` 컬럼, `.env` 의 `EMBEDDING_DIM=512`).

- OSNet 표준은 512 — 그대로면 무수정.
- 1024 차원을 쓰실 거면 알려주세요. `schema.sql` 의 `embedding_identity vector(512)` 와 `.env` 두 곳을 변경하는 마이그레이션을 따로 만들어 드립니다 (vector 차원은 ALTER 가 안 되고 *재생성* 필요해 데이터 비울 때만 가능).

## 4. curl 한 줄 — 동작 확인용

bash:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/security/detections \
  -H "Content-Type: application/json" \
  -d "{
    \"camera_id\": \"CAM_01\",
    \"tracklet_id\": \"T_TEST_1\",
    \"embedding_identity\": $(python -c "import random,json; random.seed(42); print(json.dumps([random.uniform(-1,1) for _ in range(512)]))"),
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"bbox\": [10, 20, 100, 200],
    \"event_type\": \"detection\"
  }"
```

응답 예시:
```json
{ "detection_id": 1024, "global_id": 7, "matched": true, "similarity": 0.93 }
```

## 5. Re-ID 매칭 동작 (참고)

- `find_or_create_global_id` (백엔드) 가 **최근 24시간 내 detections** 중 코사인 유사도가 가장 높은 한 명을 찾음.
- 임계값 `REID_SIMILARITY_THRESHOLD=0.85` 이상이면 같은 사람으로 `global_id` 부여, 아니면 새 사람 생성.
- 따라서 같은 사람을 여러 번 보내도 자동으로 같은 `global_id` 로 묶입니다 — 동선 추적·단골 분류의 기반.

## 6. 자동 분류 hook (백엔드 내부 동작 — 참고)

`POST /detections` 가 받으면 백엔드가 한 트랜잭션 안에서 다음을 함:
1. Re-ID 매칭 → `global_id` 결정
2. `detections` 저장
3. `persons.last_seen_at` 갱신
4. **`customer_classifier.classify_and_record`** — `person_visits` 묶기 + `visit_count`·`customer_tier` 자동 갱신
5. 알림 분기 발송 (WebSocket):
   - `event_type == "intrusion"` → `{"type":"intrusion", ...}`
   - VIP 면 → `{"type":"vip_visit", ...}`
   - 단골 *승격 순간* 1회 → `{"type":"regular_visit", ...}`

엣지는 4·5 단계를 신경 쓸 필요 없음 — `POST` 만 하면 끝.

## 7. 자주 묻는 케이스

- **Q. 한 프레임에 사람 N명이 있으면?** → N개의 POST 를 보내면 됩니다. 각 사람마다 별도 `tracklet_id`.
- **Q. 임베딩이 NaN/Inf 가 끼면?** → 백엔드는 그대로 받지만 pgvector 가 거부합니다. 엣지에서 사전 필터링 요망.
- **Q. timestamp 가 너무 옛날이면?** → 매칭 윈도우(24h) 밖이면 새 사람으로 인식될 수 있음. 시연용 백필 시 `REID_*` 윈도우 조정 가능.
- **Q. 카메라가 새로 추가되면?** → `cameras` 테이블에 행 추가가 먼저. 백엔드에 알려주세요 — `INSERT INTO cameras (camera_id, location) VALUES (...)`.

## 8. SSF 영상에서 detection 까지 — 엣지 측 권장 흐름 (참고)

> 이 절은 엣지 담당이 본인 환경 맞춰 결정. 백엔드는 결과 페이로드만 받음.

```
SSF 영상  ─[한화 백업 변환기 또는 ffmpeg]─►  프레임/MP4
   └─► YOLOv8 (사람 클래스만)                  → bbox + 신뢰도
   └─► ByteTrack (프레임 간 같은 사람 묶기)     → tracklet_id
   └─► 사람 crop 영역만 OSNet 추론             → embedding_identity (512)
   └─► HTTP POST  /api/v1/security/detections
```

각 단계 결과를 한 번에 보내도 되고, 일정 간격(예: 1초)으로 샘플링해 보내도 됩니다. 너무 자주 보내면 매칭 비용·DB 행 수가 커지니 **초당 1~3건 / 사람 기준** 정도가 적당.

## 9. 변경 이력

- 2026-05-19  v1.0 — 백엔드 자동분류 hook + 알림 분기 도입에 맞춰 v0.1 → v1.0
