# 고객 분류 & 체류·동선 특징 분석 — 설계 노트

작성: 2026-05-19 (백엔드 담당)
대상: 3인 연구팀 미팅 자료 + EYE-D 핵심 코드 인터페이스 기록

---

## 1. 오늘의 결정 한 줄

> **EYE-D 백엔드 위에 Smart Retail vertical 의 "고객 식별 + 체류 특징" 코어를 얹는다.**
> 코드는 기존 `persons / detections` 테이블을 깨지 않는 *증분 마이그레이션* 으로,
> 분석은 `person_visits / zone_visits` 두 집계 테이블 위에서만 돌게 만든다.

## 2. 새로 도입한 데이터 모델 (migration: `2026-05-19_retail.sql`)

| 항목 | 추가 위치 | 의도 |
|---|---|---|
| `persons.is_vip` (BOOL) | persons 확장 | 운영자 수동 지정 VIP. 자동 승격하지 않음(오탐 방지) |
| `persons.customer_tier` | persons 확장 | `new / returning / regular / vip` 단일 라벨 |
| `persons.visit_count` | persons 확장 | 단골 자동 승격 근거 |
| `persons.last_visit_at` | persons 확장 | 재방문 판정 + 카드 정렬용 |
| `persons.display_name`, `notes` | persons 확장 | VIP 라벨/메모 (운영자) |
| `person_visits` (신규 테이블) | — | "한 번의 방문" 단위. `duration_sec` 자동 계산 컬럼 |
| `zones` (신규 테이블) | — | 매장 내 구역 정의 (`entrance/checkout/display/...`) |
| `zone_visits` (신규 테이블) | — | 한 사람이 한 zone 에 머문 한 구간. `dwell_sec` 자동 계산 |

**왜 detections 위에서 바로 집계하지 않는가?**
`detections` 테이블은 raw event 라 행 수가 가장 빨리 증가합니다. 체류·동선 통계는 검색 빈도가 높아서 인덱스 비용을 따로 분리해야 안정적입니다. `person_visits` 1행 = 사람×방문이고, `zone_visits` 1행 = 사람×zone×체류 구간 — 이미 한 번 집계된 단위라 통계 쿼리에서 cardinality 가 한 자릿수~두 자릿수로 떨어집니다.

## 3. 고객 분류 규칙 (`services/customer_classifier.py`)

우선순위는 위에서 아래입니다.

1. `is_vip = TRUE` → **vip** (운영자 수동만)
2. `visit_count >= REGULAR_VISIT_THRESHOLD` (기본 5) → **regular**
3. `visit_count >= 2` → **returning**
4. 그 외 → **new**

**왜 VIP 는 자동 승격을 안 하나?**
방문 횟수 기반으로 VIP 를 자동 부여하면, Re-ID 매칭 오탐(다른 사람을 같은 사람으로 묶음) 때 VIP 알림이 폭주합니다. PS Center 운영자에게는 "VIP 알림 = 진짜 VIP" 라는 신뢰가 더 중요하다고 판단해 수동 지정 정책으로 정했습니다. (단골은 자동, VIP는 수동.)

**임계값 `REGULAR_VISIT_THRESHOLD = 5` 의 근거**
- 일반 상권/전시공간 단골 정의: "월 5회 이상" 이 자주 쓰이는 기준.
- `.env` 로 빼두었으므로 데이터 누적 후 ROC 곡선 보고 조정 가능.

**`REVISIT_GAP_SECONDS = 900` (15분) 의미**
같은 사람이 카메라에서 잠깐 사라졌다 다시 보이는 케이스를 같은 방문으로 묶는 임계. 너무 짧으면 한 명이 매장 한 바퀴 돌 때마다 방문 횟수가 부풀고, 너무 길면 다른 시간대 방문을 한 방문으로 합쳐 단골 승격이 늦어집니다.

## 4. 체류·동선 특징 분석 (`services/dwell_analyzer.py`)

| 함수 | 출력 | 용도 |
|---|---|---|
| `person_stats(global_id, days)` | 방문수·평균/최대 체류·시간대 분포·최근 동선 | VIP/단골 카드 디테일 |
| `hourly_traffic(days)` | 시간대별 방문/유니크 인원/평균 체류 | 매장 혼잡도 곡선 |
| `zone_summary(days)` | zone 별 방문·유니크·평균/최대 체류 | "가장 오래 머무는 구역" |
| `visit_duration_distribution(days)` | 체류시간 히스토그램 | 짧은 동선 vs 긴 동선 비율 |

이 4개 함수가 retail 라우터의 4개 통계 엔드포인트에 1:1 로 노출됩니다.

## 5. API 인터페이스 (`routers/retail.py` — prefix `/api/v1/retail`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/persons/{global_id}/vip` | VIP 지정/해제 + display_name |
| GET  | `/vips` | VIP 목록 + 최근 방문 시각 |
| GET  | `/persons?tier=vip\|regular\|...` | 등급 필터 |
| GET  | `/persons/{global_id}/stats?days=30` | 인물 디테일 |
| GET  | `/stats/hourly?days=7` | 혼잡도 곡선 |
| GET  | `/stats/zones?days=7` | zone 요약 |
| GET  | `/stats/duration?days=7` | 체류시간 분포 |

WebSocket 알림(타입 분기 `intrusion / vip_visit / regular_visit`) 는 다음 단계 — `security.post_detection` 안에 `customer_classifier.classify_and_record(...)` 호출을 hook 으로 거는 작업으로 미룹니다. 본 보안 흐름에 손대는 변경이라 한 번 더 합의가 필요하기 때문입니다.

## 6. 다른 vertical 과의 연결 (arttrace 확장 관점)

`detections` 테이블의 옵션 필드(`dwell_seconds`, `pose_keypoints`, `appearance_attrs`, `scene_context`)와 이번에 추가한 `person_visits / zone_visits` 는 그대로 arttrace 의 *해석 에이전트* 입력 페이로드로 사용 가능합니다 — 즉 같은 백엔드 코어 위에서 (보안 / Smart Retail / arttrace) 세 도메인이 같은 엔티티(`global_id`)와 같은 시계열(`detected_at`) 위에서 돌게 됩니다.

## 7. 미팅 발표 핵심 3줄

1. **같은 백엔드 코어로 3개 시장(kote/PS Center 보안, Smart Retail, arttrace) 대응이 코드 레벨에서 입증됐다** — 오늘 추가는 `+1 라우터 / +2 서비스 / +3 테이블` 만으로 끝남.
2. **VIP 는 수동, 단골은 자동** 정책으로 운영자 신뢰를 우선했고, 단골 임계값은 `.env` 한 줄 변경으로 튜닝 가능.
3. **체류·동선 분석은 raw detections 가 아니라 person_visits/zone_visits 집계 위에서만** 돌게 분리해 성능·확장성을 같이 확보.

## 8. 남은 위험·확인 사항

- `zone_visits` 행을 만드는 엣지/백엔드 책임 분담 — 엣지가 zone in/out 이벤트를 직접 보내는지, 백엔드가 detections 로부터 추론할지 합의 필요.
- `customer_classifier.classify_and_record` 의 hook 위치(`security.post_detection`) — 본 보안 흐름과 결합되므로 트랜잭션·예외 처리 정책 합의 필요.
- 단골 임계값 5회는 가설값. 1~2주 데이터로 실측 후 조정.
