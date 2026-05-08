# [PRD] Jetson Orin Nano 기반 실내 인원 추적 및 중앙 관리 시스템

## 1. 프로젝트 개요 (Project Overview)
본 프로젝트는 NVIDIA Jetson Orin Nano Developer Kit을 활용하여 실내 환경의 3개 채널 비디오 스트림에서 사람을 감지, 추적하고 특징 벡터를 추출합니다. 에지 단에서 처리된 실시간 데이터는 중앙 관리 서버(FastAPI/PostgreSQL)로 전송되어 영구 저장되며, 웹 대시보드를 통해 특정 인물 검색 및 실내 유동 인구 통계 데이터를 제공하는 고성능 에지-클라우드 협업 AI 시스템 구축을 목표로 합니다.

## 2. 주요 목적 (Key Objectives)
- **실내 최적화**: 실내 조명 및 구조적 특성에 최적화된 사람 감지 및 재식별.
- **에지-서버 협업**: Jetson에서 고부하 추론을 처리하고, 서버에서 데이터 관리 및 통계 시각화를 담당하여 부하 분산.
- **인물 검색 및 재식별**: 카메라 간 동일 인물 식별(Cross-camera Tracking)이 가능한 Re-ID 데이터베이스 구축.
- **자원 효율성**: Orin Nano의 Unified Memory를 고려한 파이프라인 최적화 및 FastAPI 비동기 처리.

## 3. 기능적 요구사항 (Functional Requirements)

### 3.1 입력 및 전처리
- 3채널 실내 IP 카메라(RTSP) 수신 (1080p, 15~20fps).
- RTSP 스트림 재연결 및 채널 상태 모니터링, 프레임 손실 보정.
- 실내 조명 대응 자동 화이트밸런스, 노이즈 제거 및 DeepStream 입력용 포맷 변환.

### 3.2 Edge Zone: 탐지 · 추적 · Re-ID
- **YOLO Detection**: 사람 전용 YOLOv8n/v10n 모델, TensorRT INT8 최적화.
- **ByteTrack**: 실내 Occlusion 대응 및 객체 고유 ID 유지.
- **Re-ID Extraction**: Torchreid 기반 OSNet-light 모델로 128~512차원 특징 벡터 생성.
- **Local Vector DB**: Qdrant 또는 Milvus Lite를 활용한 에지단 벡터 캐싱 및 1차 유사도 비교.

### 3.3 Central Management Zone: 서버 및 저장
- **Event Data 전송**: 감지된 이벤트(ID, Timestamp, Vector, Snapshot)를 LAN을 통해 서버로 전송.
- **FastAPI Server**: 에지 장치 데이터 수신 및 처리 API 제공.
- **PostgreSQL (DB)**: 이벤트 메타데이터 및 분석 결과 영구 저장 (PGVector 확장 고려).
- **File Storage**: 인물 스냅샷 이미지 파일 저장.

### 3.4 분석 및 대시보드
- **통계 분석**: Entrance/Exit 카운팅(Line Crossing), 영역별 체류 시간(Dwell Time) 측정.
- **Web Dashboard**: 시간대별 유동 인구 보고서, 실시간 인원 카운팅, 특정 인물 과거 동선 검색.

## 4. 기술 사양 (Technical Specifications)

| 항목 | 세부 사항 |
| --- | --- |
| Edge Device | NVIDIA Jetson Orin Nano Developer Kit (8GB RAM) |
| Server | x86 Linux Server (FastAPI, PostgreSQL, Docker) |
| OS / SDK | JetPack 6.x, DeepStream 7.0, TensorRT 10.x |
| Model Pipeline | PyTorch (Torchreid) → ONNX → TensorRT |
| Models | YOLOv8n (Detection), OSNet-light (Re-ID) |
| Databases | Qdrant (Local Vector), PostgreSQL (Central DB) |
| Communication | HTTP/JSON (Event), WebSocket (Dashboard) |

## 5. 시스템 인터페이스 및 DB 설계

### 5.1 FastAPI 주요 엔드포인트
- `POST /v1/events` : 에지 장치로부터 이벤트 및 벡터 수집.
- `GET /v1/analytics/daily` : 당일 통계 데이터(피크 타임, 총 방문자 등) 조회.
- `POST /v1/search/identity` : 이미지 업로드 기반 동일 인물 과거 이력 검색.

### 5.2 PostgreSQL 주요 스키마
- `cameras` : 에지 장치 정보 (ID, 위치, IP 등).
- `events` : 개별 감지 이벤트 (카메라 ID, 로컬 ID, 타임스탬프, 이미지 경로, 벡터).
- `daily_stats` : 시간대별/카메라별 출입 및 체류 통계 집계.

## 6. 비기능적 요구사항 (Non-Functional Requirements)

| 항목 | 목표 |
| --- | --- |
| 성능 | 3채널 통합 45~60 FPS 유지 (채널당 15~20 FPS) |
| 응답성 | 벡터 검색(10,000개 기준) 50ms 이내, 서버 대시보드 표출 500ms 이내 |
| 신뢰성 | ID Switching 5% 이하, False Positive 5% 이하 |
| 가용성 | RTSP 자동 복구 및 서비스 가동 시간 99% 이상 |
| 보안 | 데이터 암호화, 접근 제어, 개인정보 비식별화(Blurring) 옵션 |

## 7. 운영 시나리오 및 데이터 플로우
1. **입력**: 3개 RTSP 스트림 수신 → 전처리(노이즈 제거, 정규화).
2. **추론**: YOLO 사람 감지 → ByteTrack ID 할당 → OSNet-light 특징 추출.
3. **전송**: 추출된 벡터와 스냅샷을 LAN을 통해 FastAPI 서버로 전송.
4. **저장**: 서버는 PostgreSQL 및 파일 스토리지에 데이터 기록.
5. **활용**: 관리자가 웹 대시보드에서 통계 확인 및 특정 인물 검색 수행.

## 8. 요구사항 우선순위 (Prioritization)
1. **필수 (Must-have)**: 3채널 RTSP 연동, 사람 감지/추적/Re-ID 파이프라인, 중앙 서버 데이터 전송 및 저장, Orin Nano 8GB 안정 운영.
2. **우선순위 높음 (Should-have)**: Cross-camera 매칭 및 시간/공간 보정, 웹 기반 실시간 대시보드, RTSP 장애 자동 복구, Docker 기반 배포.
3. **우선순위 낮음 (Could-have)**: 인물 이미지 자동 비식별화, 이상 행동 감지(쓰러짐 등), 히트맵 분석.

## 9. 리스크 (Risks)
- **성능 한계**: 3채널 동시 처리 시 Orin Nano의 GPU/메모리 자원 고갈 가능성.
- **네트워크 안정성**: LAN 환경 불안정 시 데이터 전송 지연 및 유실.
- **환경 요인**: 실내 조명 변화나 복잡한 동선으로 인한 Re-ID 정확도 저하.

## 10. 완료 기준 (Definition of Done)
- 3채널 RTSP 입력이 안정적으로 연결되고 45 FPS 이상을 유지한다.
- Re-ID Rank-1 정확도가 80% 이상이며, ID Switching이 5% 이내이다.
- 서버 DB에 데이터가 정상 적재되고 웹 대시보드에서 500ms 이내에 갱신된다.
- Docker 기반으로 전체 시스템이 배포 가능하며 모니터링이 동작한다.
