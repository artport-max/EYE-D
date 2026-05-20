# EYE-D: 실내 인원 추적 관리 시스템

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

본 프로젝트는 현장에 설치되는 **에지 파이프라인(edge)**과 이들이 전송하는 보안/비즈니스 분석 데이터를 실시간 수집 및 가시화하는 **중앙 관리 서버(server)**로 구성되어 있습니다.

---

### 1. 백엔드 중앙 관리 서버 (Central Server) 실행 방법

중앙 서버는 PostgreSQL (pgvector 포함) 데이터베이스와 FastAPI API 웹 서버로 구동됩니다.

#### 1.1. 데이터베이스 기동 (Docker Compose)
`server/` 디렉토리로 이동하여 환경 설정 템플릿을 활성화하고 도커 컴포즈로 DB 컨테이너를 올립니다.

* **Linux / macOS (Bash) 및 Windows (Git Bash):**
  ```bash
  cd server
  cp .env.example .env
  docker compose up -d
  ```

* **Windows (PowerShell):**
  ```powershell
  cd server
  Copy-Item .env.example .env
  docker compose up -d
  ```

*(호스트 포트 `5433`으로 PostgreSQL 서비스가 맵핑되어 열립니다.)*

#### 1.2. 초기 데이터베이스 마이그레이션 적용
최초 기동 시점 스키마 외에 리테일 분석을 위한 마이그레이션 스크립트를 데이터베이스에 적재합니다.

* **Linux / macOS (Bash):**
  ```bash
  cat app/db/migrations/2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
  ```

* **Windows (PowerShell):**
  ```powershell
  Get-Content .\app\db\migrations\2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
  ```

#### 1.3. FastAPI 서버 가동
파이썬 가상환경을 생성하고 의존 패키지를 받아 가동시킵니다.

* **Linux / macOS (Bash):**
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  uvicorn app.main:app --reload
  ```

* **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  uvicorn app.main:app --reload
  ```

*(서버는 `http://localhost:8000` 에서 API 수신 상태를 활성화합니다.)*

---

### 2. 에지 AI 파이프라인 (Edge Pipeline) 실행 방법

에지 파이프라인은 RTSP 스트림이나 비디오 데이터로부터 인물 탐지, ByteTrack 추적, OSNet 특징 벡터 추출을 거쳐 실시간으로 중앙 서버에 전달합니다.

#### 2.1. 로컬 Vector DB (Qdrant) 기동
특징 벡터 로컬 캐싱 및 매칭을 위해 로컬 Qdrant를 활성화합니다. (만약 Qdrant를 올리지 않아도 파이프라인이 자동 인식하여 '로컬 DB 없는 추론 모드'로 안전하게 Fallback 구동됩니다.)
```bash
# 프로젝트 최상단 디렉토리에서 실행
docker-compose up -d qdrant
```

#### 2.2. 에지 파이프라인 설치 및 실행
```bash
# 엣지 디렉토리로 이동
cd edge

# 가상환경 활성화 (Conda 환경 권장)
conda activate cv_poc

# 필수 패키지 설치
pip install -r ../requirements.txt

# 에지 파이프라인 가동 (기본 백엔드 http://localhost:8000으로 데이터 자동 전송)
python main.py --source ../data/16300000.avi --camera-id CAM_01 --display
```

**실행 주요 인자(Arguments)**
- `--source`: 분석할 소스. RTSP 주소, 비디오 파일 경로 또는 웹캠 ID (기본값: `0`)
- `--camera-id`: 카메라 고유 식별자 (기본값: `CAM_01`, 서버 DB에 사전 등록된 대문자 식별자 사용 권장)
- `--tensorrt`: GPU 가속(TensorRT) 엔진 사용 여부
- `--display`: 처리 결과를 화면에 시각화하여 확인 (UI 지원 환경에서만 동작)

---

## 📄 추가 문서
시스템 요구사항, 목표 성능 (45~60 FPS), 비기능적 요구사항 및 상세 QA 체크리스트에 대한 자세한 내용은 [docs/PRD.md](./docs/PRD.md) 문서를 참고해 주시기 바랍니다.