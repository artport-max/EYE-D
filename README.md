# EYE-D: Jetson Orin Nano 기반 실내 인원 추적 및 중앙 관리 시스템

본 프로젝트는 실내 환경의 3개 채널 비디오 스트림에서 사람을 감지, 추적하고 특징 벡터를 추출하여 서버와 에지 단에서 분산 처리하는 에지-클라우드 협업 AI 시스템입니다.

---

## 🎯 주요 기능 및 특징

### 1. Edge Zone (Jetson Orin Nano)
- **실시간 비디오 처리**: 3채널 RTSP IP 카메라 연동 (1080p, 15~20fps)
- **탐지 및 추적**: YOLOv8n(TensorRT INT8 최적화)을 이용한 사람 탐지 및 ByteTrack 알고리즘을 통한 지속적인 추적
- **재식별(Re-ID)**: Torchreid(OSNet-light)를 활용해 인물의 특징 벡터(128~512차원) 추출
- **Local Vector 연산**: Qdrant 또는 Milvus Lite 기반의 에지단 벡터 캐싱 및 1차 유사도 비교

### 2. Central Management Zone (Server)
- **이벤트 수집**: FastAPI 기반 고성능 비동기 API 서버
- **데이터베이스 영구 저장**: PostgreSQL(PGVector 확장)을 통한 메타데이터 및 특징 벡터 관리
- **스토리지**: 인물 스냅샷 이미지의 분산 파일 저장소 연동

### 3. Dashboard (Web)
- **통계 분석 시각화**: 구역별 체류 시간(Dwell Time) 및 인원 출입 카운팅(Line Crossing) 제공
- **인물 검색**: 저장된 벡터를 이용한 카메라 간 Cross-camera Tracking 및 특정 인물의 과거 동선 조회

---

## 🛠 기술 스택 (Tech Stack)

### Edge Device
- **H/W**: NVIDIA Jetson Orin Nano Developer Kit (8GB RAM)
- **OS/SDK**: JetPack 6.x, DeepStream 7.0, TensorRT 10.x
- **Pipeline**: PyTorch → ONNX → TensorRT

### Backend / Server
- **Server**: x86 Linux Server, Docker Compose
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL (Central DB), Qdrant (Local Vector DB)
- **Communication**: HTTP/JSON (Event), WebSocket (Dashboard 실시간 연동)

---

## 📂 프로젝트 폴더 구조

```text
EYE-D/
├── data/               # Edge와 Server 공통 데이터 폴더 (스냅샷, 테스트 비디오 등)
├── edge/               # Jetson Orin Nano 기반 Edge 처리부
│   ├── config/         # DeepStream, TensorRT 및 파이프라인 설정
│   ├── models/         # YOLO, OSNet 모델 등 가중치 파일 저장소
│   ├── notebooks/      # 모델 테스트 및 프로토타이핑용 주피터 노트북
│   ├── src/
│   │   ├── core/       # 메인 파이프라인(RTSP 처리, 서버 전송) 모듈
│   │   ├── database/   # Local Vector DB 연동
│   │   ├── detection/  # YOLO 기반 객체 탐지
│   │   ├── reid/       # Torchreid 기반 Re-ID
│   │   └── tracking/   # ByteTrack 적용
│   └── tests/          # 단위/통합 테스트
├── server/             # FastAPI 기반 중앙 관리 서버
│   ├── app/
│   │   ├── api/        # 엔드포인트 라우터
│   │   ├── core/       # 환경 설정, 보안
│   │   ├── db/         # DB 세팅 (PostgreSQL, SQLAlchemy)
│   │   ├── models/     # DB 모델 및 ORM
│   │   ├── schemas/    # Pydantic 스키마
│   │   └── services/   # 비즈니스 로직
│   └── tests/          # 단위/통합 테스트
├── dashboard/          # 통계 및 검색을 위한 프론트엔드 대시보드
│   ├── public/
│   └── src/
├── docs/               # 문서 저장소
│   ├── PRD.md          # 상세 시스템 요구사항 명세서
└── docker-compose.yml  # 시스템 통합 배포용 도커 컴포즈 파일
```

---

## 📊 시스템 데이터 플로우
1. 3개 RTSP 스트림 영상 수신 및 전처리 (노이즈 제거 등)
2. Jetson에서 YOLO 추론 (사람 감지) -> ByteTrack 추적 -> OSNet-light 특징 추출
3. 특징 벡터와 스냅샷 이미지를 FastAPI 서버로 전송
4. PostgreSQL에 데이터를 기록 및 누적
5. 웹 대시보드에서 분석된 통계 확인 및 과거 이력 검색 수행

---

## 🚀 설치 및 실행 방법 (Installation & Usage)

### 1. 환경 설정 및 패키지 설치
- **Anaconda**를 사용하여 격리된 가상 환경에서 작업하는 것을 권장합니다.
- Python 3.10 이상이 필요합니다.

```bash
# conda 환경 생성 및 활성화
conda create -n cv_poc python=3.10
conda activate cv_poc

# 필수 패키지 설치
pip install ultralytics torch torchvision torchaudio opencv-python numpy
pip install qdrant-client fastapi uvicorn psutil
# (ByteTrack 및 Torchreid는 공식 저장소 가이드에 따라 별도로 추가 설치를 진행합니다.)
```

### 2. 인프라 준비 (로컬 Vector DB)
에지단에서 생성되는 특징 벡터(Re-ID)의 로컬 캐싱 및 매칭을 위해 Qdrant DB를 실행해야 합니다.

```bash
# docker-compose를 이용해 백그라운드에서 Qdrant 실행
docker-compose up -d qdrant
```

### 3. Edge Pipeline 실행
모든 준비가 완료되었다면 프로젝트 최상위 경로에서 `main.py`를 통해 파이프라인을 구동합니다.

```bash
# 프로젝트 최상단 디렉토리에서 실행
PYTHONPATH=. python main.py --source 0 --camera-id cam_01 --display
```

**실행 주요 인자(Arguments)**
- `--source`: 분석할 영상 소스. RTSP 주소, 비디오 파일 경로 또는 로컬 웹캠 ID (기본값: `0`)
- `--camera-id`: 현재 카메라의 고유 식별자 (기본값: `cam_01`)
- `--tensorrt`: TensorRT 엔진 활성화 (Jetson 환경 최적화)
- `--display`: 처리 결과를 화면에 시각화하여 확인 (UI 지원 환경에서만 동작)

---

## 📄 추가 문서
시스템 요구사항, 목표 성능 (45~60 FPS), 비기능적 요구사항 및 상세 QA 체크리스트에 대한 자세한 내용은 [docs/PRD.md](./docs/PRD.md) 문서를 참고해 주시기 바랍니다.