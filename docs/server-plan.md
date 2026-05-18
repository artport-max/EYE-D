# EYE-D Server Implementation Plan

본 문서는 `PRD.md`를 기반으로 백엔드(서버) 및 연동에 관해 처음 수립된 전체 개발 계획(Plan)을 정리한 것입니다. 진행 상황에 따라 체크리스트를 관리합니다.

## Phase 1: 기반 API 및 UI 연동 (완료)
- [x] **Analytics API 구현**: 일일 방문자 수 및 시간대별 분포 통계 제공 (`/api/v1/analytics/daily`)
- [x] **Search API 기반 구현**: 더미 벡터를 활용한 `pgvector` 기반 코사인 유사도 검색 구현 (`/api/v1/search/identity_by_vector`)
- [x] **Frontend UI 대시보드 연동**: React/Vite 기반 UI에서 실시간 통계 데이터 및 히스토리 차트 연동
- [x] **Mocking E2E 테스트**: 대량의 가상 트래픽 주입 스크립트(`bulk_mock_sender.py`)를 통한 DB 적재 및 UI 정상동작 검증

## Phase 2: 실제 모델(OSNet) 서버 통합 (진행 예정)
- [ ] **PyTorch / OSNet 연동**: 서버 단에서 모델을 로드하여 업로드된 이미지 파일에서 사람 객체의 특징 벡터(512차원)를 추출하는 파이프라인 구성
- [ ] **이미지 검색 API 완성**: 프론트엔드에서 이미지를 업로드받아 서버에서 임베딩을 추출한 뒤, 유사도 검색 로직과 연결하는 엔드포인트 활성화 (`/api/v1/search/identity`)
- [ ] **모델 로드 최적화**: API 호출 때마다 모델을 부르지 않도록, 서버 기동 시(`lifespan`) OSNet 가중치를 메모리에 캐싱하여 지연 시간(Latency) 최소화

## Phase 3: Edge 디바이스(Jetson) 실제 데이터 연동
- [ ] **엣지 파이프라인 통합**: 더미 스크립트가 아닌, 엣지 보드에서 실제 영상 스트림으로부터 BBox와 벡터를 추출해 백엔드로 전송하는 로직 디버깅
- [ ] **Occupancy(밀집도/점유율) 동적 계산**: 일정 시간 내 포착 후 사라지지 않은 활성 `global_id` 수를 집계하여 실제 건물 내 체류 인원을 산출하는 비즈니스 로직 추가
- [ ] **Re-ID 매칭 최적화**: 실제 엣지 데이터를 바탕으로 코사인 유사도 임계값(Threshold) 튜닝 (현재 `.env` 기준 0.85)

## Phase 4: UI 디테일 및 안정화
- [ ] **예외/에러 핸들링**: 이미지 검색 결과가 없을 때의 UI 대응 ("No result found") 및 서버 통신 장애 시 화면 처리
- [ ] **DB 검색 성능 최적화**: 데이터가 만 건 이상 누적될 경우를 대비한 `pgvector` 인덱싱(`ivfflat`) 효율 모니터링
- [ ] **최종 패키징**: 운영(Production) 배포를 고려한 환경 변수 정리 및 Docker 기반 통합 실행 가이드라인 작성
