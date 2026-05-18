# EYE-D Edge Implementation Plan

본 문서는 `PRD.md`를 기반으로 현장 카메라(Edge Device) 단의 사람 탐지, 특징 추출 및 서버 통신에 관해 수립된 개발 계획(Plan)을 정리한 것입니다. 진행 상황에 따라 체크리스트를 관리합니다.

## Phase 1: 기반 파이프라인 구성 (로컬/개발 환경)
- [x] **객체 탐지 (Person Detection)**: 비디오 스트림이나 동영상 파일에서 사람 객체의 Bounding Box(BBox)를 실시간으로 탐지 (`edge/src/core/detector.py` 완료)
- [x] **특징 추출 (Feature Extraction)**: 탐지된 사람 영역 이미지를 크롭하여 OSNet 모델에 통과시키고 512차원 임베딩 벡터 추출 (`edge/src/core/reid_extractor.py` 완료)
- [x] **백엔드 통신 연동**: 추출된 데이터(`camera_id`, `timestamp`, `bbox`, `embedding_identity`)를 JSON 포맷으로 묶어 서버의 API 엔드포인트로 전송하는 HTTP 클라이언트 및 NullSender 연동 인터페이스 구현 (`edge/src/core/pipeline_runner.py` 완료)
- [x] **단일 스트림 테스트**: 샘플 CCTV 영상을 활용하여 탐지-추출-전송의 전체 파이프라인이 로컬 PC 환경에서 병목 없이 정상 동작하는지 단위 테스트 및 격리 테스트 검증 완료 (`tests/unit/test_pipeline_runner.py` 완료)

## Phase 2: 실제 Edge 하드웨어(Jetson 등) 최적화
- [x] **하드웨어 가속 (TensorRT / ONNX)**: 무거운 딥러닝 모델(YOLO, OSNet)을 엣지 디바이스의 GPU 자원을 최대한 활용할 수 있는 포맷으로 변환하여 추론 속도(FPS) 극대화 (YOLO TensorRT 자동 변환 및 OSNet ONNX 가속화 완료)
- [x] **파이프라인 병렬화**: 카메라 프레임 읽기(I/O), 딥러닝 추론, 서버 전송 로직을 각각 별도의 스레드/프로세스로 분리하여 딜레이 최소화 (생산자-소비자 큐 패턴 및 최신 프레임 보존 Drop 전략 완료)
- [x] **네트워크 복원력 (Resilience)**: 일시적인 와이파이/네트워크 단절 시 데이터를 버려버리지 않고 로컬 버퍼(Queue 또는 SQLite)에 임시 저장했다가 통신 회복 시 재전송하는 로직 구현 (SQLite 기반 로컬 큐 및 백그라운드 자동 전송 재시도 완료)

## Phase 3: 데이터 품질 고도화 및 실환경 적용
- [x] **객체 추적 (Object Tracking) 결합**: 매 프레임마다 벡터를 전송하지 않고, BoxMOT 트래커(ByteTrack/BotSORT 등)를 결합해 동일 인물의 궤적(Tracklet)에 고유 ID를 부여하고 정규화 처리 완료 (`edge/src/core/tracker.py` 완료)
- [x] **다중 카메라 수용**: 하나의 Edge 보드에서 여러 대의 IP 카메라(RTSP 스트림)를 동시에 디코딩하고 추론할 수 있는 Multi-Stream 처리 아키텍처 적용 (단일 GPU 추론 모델 공유 및 비동기 멀티리더 프레임 드랍 큐 기반 MultiStreamPipelineRunner 구현 완료)
- [x] **악조건 환경 대응 테스트**: 역광, 야간(IR), 저해상도 등 다양한 실제 현장 조건에서 탐지율 및 벡터 품질(Re-ID 정확도) 튜닝 (ImagePreprocessor의 적응형 감마 변환, 동적 clipLimit CLAHE 및 ReIDExtractor 연동형 Unsharp Masking ROI Sharpening 보정 엔진 구현 및 검증 완료)
