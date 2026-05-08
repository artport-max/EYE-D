# EYE-D 프로젝트 향후 개발 TO-DO 리스트

현재 Edge Zone 파이프라인의 핵심 로직(YOLO, ByteTrack, OSNet, Qdrant 연동, Analytics)이 구현된 상태입니다. 이후 상용(Production) 수준의 완성을 위해 다음 작업들이 필요합니다.

## 1. Edge Zone (에지 기능 보완)
- [ ] **중앙 서버(Server Zone) 데이터 전송 로직 구현**
  - 추출된 Re-ID 벡터, 출입 메타데이터(출입 시간, 카메라 ID 등)를 중앙 서버(FastAPI)로 전송(`HTTP POST` 또는 `WebSocket` 사용).
- [ ] **인물 스냅샷 저장 및 원격 업로드 로직**
  - 분석에 활용된 객체 이미지(ROI)를 캡처하여 분산 스토리지(MinIO, AWS S3 등) 혹은 중앙 서버로 업로드하는 기능 추가.
- [ ] **에러 폴백(Mocking) 및 의존성 처리 개선**
  - `pipeline_runner.py` 내의 `tests.harness.mocks` 의존성을 제거하고, 실제 패키지가 없을 때 에러 로그를 명확히 남기거나 재시도하는 견고한 예외 처리로 교체.

## 2. Server Zone (중앙 관리 서버 구축)
- [ ] **FastAPI 기반 수신 서버 세팅**
  - 에지 디바이스에서 보내오는 메타데이터와 벡터를 수신할 REST API 엔드포인트 구축.
- [ ] **중앙 Database 연동 (PostgreSQL/PGVector)**
  - 여러 카메라(Edge)에서 수집된 데이터를 영구적으로 저장하기 위한 DB 스키마 설계 및 연동.

## 3. Dashboard (프론트엔드 및 시각화)
- [ ] **데이터 시각화 대시보드 구축**
  - 중앙 서버의 통계 데이터(구역별 체류 시간, 출입 카운트)를 웹 화면에 시각화.
- [ ] **인물 추적(Cross-camera Tracking) UI**
  - 특정 인물의 이미지나 벡터를 이용해 과거 동선과 출입 이력을 검색하는 기능 연동.
