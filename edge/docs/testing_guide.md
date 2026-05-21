# EYE-D Edge — 테스트 실행 가이드

> 설정 파일: `edge/pytest.ini`

---

## 목차 (Table of Contents)

* [1. 단위 테스트 (Pytest)](#1-단위-테스트-pytest)
  * [1.1. 사전 준비](#11-사전-준비)
  * [1.2. 기본 실행](#12-기본-실행)
  * [1.3. 선택적 실행](#13-선택적-실행)
  * [1.4. 출력 옵션](#14-출력-옵션)
  * [1.5. 커버리지 측정 (선택)](#15-커버리지-측정-선택)
  * [1.6. pytest.ini 설정 내용](#16-pytestini-설정-내용)
  * [1.7. 테스트 파일 및 폴더 위치 구조](#17-테스트-파일-및-폴더-위치-구조)
* [2. 실시간 인터랙티브 비주얼 데모 테스트 (tools/visual_demo.py)](#2-실시간-인터랙티브-비주얼-데모-테스트-toolsvisual_demopy)
  * [2.1. 실행 명령](#21-실행-명령)
  * [2.2. 키보드 인터랙티브 조작 보드](#22-키보드-인터랙티브-조작-보드)
* [3. 로컬 엣지 파이프라인 구동 테스트 (main.py)](#3-로컬-엣지-파이프라인-구동-테스트-mainpy)
  * [3.1. 사전 준비](#31-사전-준비)
  * [3.2. 실행 명령어 (edge/ 디렉토리 기준)](#32-실행-명령어-edge-디렉토리-기준)
  * [3.3. 모니터링 단축키 & 제어](#33-모니터링-단축키-제어)
  * [3.4. Qdrant 수집 데이터 조회 및 확인 방법](#34-qdrant-수집-데이터-조회-및-확인-방법)
  * [3.5. 실제 백엔드 서버(FastAPI) 전송 검증 방법](#35-실제-백엔드-서버fastapi-전송-검증-방법)
* [4. 실기기(Jetson) 배포 및 운영 프로세스 (Production Deployment)](#4-실기기jetson-배포-및-운영-프로세스-production-deployment)
  * [4.1. 모델 하드웨어 가속 최적화 (TensorRT 변환)](#41-모델-하드웨어-가속-최적화-tensorrt-변환)
  * [4.2. 컨테이너 기반 패키징 (Dockerization)](#42-컨테이너-기반-패키징-dockerization)
  * [4.3. 엣지 디바이스 프로비저닝 (환경 설정)](#43-엣지-디바이스-프로비저닝-환경-설정)
  * [4.4. 무중단 운영 및 업데이트 관리](#44-무중단-운영-및-업데이트-관리)
  * [4.5. 원격 모니터링 및 장애 감지](#45-원격-모니터링-및-장애-감지)
* [5. RTSP 다채널 스트리밍 모의 테스트 (Mediamtx + FFmpeg)](#5-rtsp-다채널-스트리밍-모의-테스트-mediamtx--ffmpeg)
  * [5.1. Mediamtx (RTSP 미디어 서버) 설정](#51-mediamtx-rtsp-미디어-서버-설정)
  * [5.2. FFmpeg을 이용한 다채널 무한 루프 송출](#52-ffmpeg을-이용한-다채널-무한-루프-송출)
  * [5.3. 에지 노드(수신 측) 정상 수신 검증](#53-에지-노드수신-측-정상-수신-검증)
  * [5.4. 에지 AI 파이프라인 연동 (main.py 구동 예시)](#54-에지-ai-파이프라인-연동-mainpy-구동-예시)

---

## 1. 단위 테스트 (Pytest)

엣지 핵심 모듈(파이프라인 러너, 예외 처리, 비동기 다중 스트림 제어 등)의 로직 무결성을 검증하기 위한 단위 및 통합 테스트 가이드입니다.

### 1.1. 사전 준비

```bash
# 1. conda 환경 활성화
conda activate <virtual env>

# 2. edge/ 디렉토리로 이동 (반드시 이 위치에서 실행)
cd <PROJECT_ROOT_DIR>/edge

# 3. pytest 미설치 시
pip install pytest
```

### 1.2. 기본 실행

```bash
# 전체 단위 테스트 실행
python -m pytest tests/unit/test_pipeline_runner.py

# 전체 tests/ 하위 모든 테스트 실행
python -m pytest
```

### 1.3. 선택적 실행

```bash
# 특정 테스트 클래스만
python -m pytest tests/unit/test_pipeline_runner.py::TestProcessFrame

# 특정 테스트 함수 하나만
python -m pytest tests/unit/test_pipeline_runner.py::TestPipelineRunnerWithDB::test_db_upsert_failure_does_not_crash_pipeline

# 키워드 매칭 (테스트 이름에 'db'가 포함된 것만)
python -m pytest -k "db"

# 키워드 제외 (batch 관련 제외)
python -m pytest -k "not batch"
```

### 1.4. 출력 옵션

```bash
# 기본 (pytest.ini에 -v --tb=short 적용됨)
python -m pytest

# 더 상세한 실패 정보
python -m pytest --tb=long

# 조용하게 (PASSED/FAILED 요약만)
python -m pytest -q

# 첫 번째 실패에서 즉시 중단
python -m pytest -x

# 실패한 테스트만 재실행
python -m pytest --lf
```

### 1.5. 커버리지 측정 (선택)

```bash
# pytest-cov 설치
pip install pytest-cov

# 커버리지 포함 실행
python -m pytest --cov=src --cov-report=term-missing
```

### 1.6. pytest.ini 설정 내용

```ini
[pytest]
testpaths = tests        # 테스트 루트
pythonpath = .           # src/ 임포트 경로 설정
addopts = -v --tb=short  # 기본 출력 옵션
```

> ⚠️ 반드시 `edge/` 디렉토리에서 실행해야 `pytest.ini`가 인식됩니다.

### 1.7. 테스트 파일 및 폴더 위치 구조

```
edge/
├── main.py                                 # 엣지 AI 파이프라인 실행 메인 진입점 (YOLO, Tracker, Re-ID 연동)
├── pytest.ini                              # 테스트 설정 (testpaths, pythonpath)
├── src/                                    # 엣지 서비스 코어 소스코드
│   ├── core/                               # 알고리즘 오케스트레이터 및 전처리/추론 모듈
│   └── infrastructure/                     # DB 클라이언트, 네트워크 전송, 시스템 모니터링 등 인프라
├── tools/                                  # 시각화 데모 툴 등 테스트 보조 도구
└── tests/
    ├── conftest.py                         # 공통 피스처 (frame, tracks, mock_db 등)
    ├── harness/
    │   ├── fixtures.py                     # 더미 데이터 생성 함수
    │   └── mocks.py                        # Mock 클래스 (DB, HTTP, Detector 등)
    └── unit/
        ├── test_null_objects.py            # Null Object 패턴 관련 단위 테스트 (20개)
        ├── test_pipeline_runner.py         # PipelineRunner 흐름 제어 단위 테스트 (21개)
        ├── test_phase2_resilience.py       # ONNX 하드웨어 가속 및 네트워크 복원력 검증 (4개)
        ├── test_phase3_multistream.py      # 비동기 모델 공유 다중 카메라 제어 검증 (1개)
        ├── test_phase3_harsh_conditions.py # 야간/역광/저해상도 복원력 수치 검증 (3개)
        └── test_e2e_pipeline.py            # 탐지➔추적➔보정➔임베딩 E2E 연쇄 검증 (2개)
```

---

## 2. 실시간 인터랙티브 비주얼 데모 테스트 (tools/visual_demo.py)

단위 테스트를 넘어, 실제 영상 혹은 자율 합성된 가상 환경 하에서 실시간 엣지 파이프라인 보정 효과를 눈으로 직접 보며 인터랙티브하게 검증할 수 있는 통합 시각화 데모 도구입니다.

### 2.1. 실행 명령

반드시 `conda activate <virtual env>` 활성화 및 `edge/` 디렉토리로 이동한 후 기동하십시오.

```bash
# 옵션 A. 가상 악조건(저조도 야간, 역광 루프) 자율 시뮬레이션 데모 가동 (추천)
python tools/visual_demo.py

# 옵션 B. 실제 소유한 로컬 비디오 파일(.mp4 등)을 입력으로 주어 데모 가동
python tools/visual_demo.py --video <테스트비디오경로>
```

### 2.2. 키보드 인터랙티브 조작 보드

시각화 윈도우 창이 떠 있는 상태에서 아래의 단축키를 눌러 실시간으로 필터 적용 전후를 사이드-바이-사이드로 비교할 수 있습니다.

| 단축키 | 작동 필터 | 튜닝 보정 효과 설명 |
|:---:|---|---|
| **`N`** | **야간 저조도 모드 (Night)** | 감마 1.6 보정 LUT 테이블을 적용하여, 저조도 속 어두운 피사체를 화사하고 뚜렷하게 밝힙니다. |
| **`B`** | **역광 보정 모드 (Backlight)** | 명암 편차가 심해 어둡게 타버린 인물 그늘 영역에 CLAHE를 가중 적용해 윤곽을 복구합니다. |
| **`S`** | **저해상도 ROI 선명화 (Sharpen)** | 우측 하단 돋보기 창에 언샤프 마스킹 선명도를 적용해, 인물 크롭 텍스처를 34% 이상 선명히 복원합니다. |
| **`Q` / `ESC`** | **데모 정지 및 종료** | 실시간 데모의 윈도우를 안전하게 닫고 모든 하드웨어 자원을 해제합니다. |

---

## 3. 로컬 엣지 파이프라인 구동 테스트 (main.py)

실제 임베디드 디바이스(Jetson Orin Nano 등)에 배포하기 전, 로컬 개발 PC 환경에서 전체 에지 AI 파이프라인(객체 탐지, 동일인 추적, Re-ID 특징 벡터 추출 및 분석)의 기능과 성능을 사전에 실환경에 가깝게 시뮬레이션하여 검증합니다.

### 3.1. 사전 준비

#### 3.1.1. 가상 환경 활성화
```bash
conda activate <virtual env>
```

#### 3.1.2. 로컬 Qdrant (벡터 DB) 구동 및 초기화 (선택 사항)
엣지의 Re-ID 특징 벡터 로컬 캐싱 및 검색 연동 테스트를 위해서는 로컬 Qdrant 서버가 필요합니다. 만약 DB가 구동되지 않은 경우, **파이프라인이 자동으로 감지하여 '로컬 DB 없는 순수 추론 모드'로 안전하게 Fallback하여 진행**됩니다.

##### 3.1.2.1. Qdrant 신규 구동
데이터 관리의 일관성을 위해 **프로젝트 엣지 디렉토리(`EYE-D/edge`)에서 실행**하는 것을 권장합니다. (현재 실행 경로 하위에 `qdrant_storage/` 데이터 폴더가 생성됩니다.)

```bash
# 프로젝트 엣지 디렉토리(EYE-D/edge)에서 실행
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

##### 3.1.2.2. 트러블슈팅: 포트 충돌 및 컬렉션 강제 초기화
이미 다른 Qdrant 컨테이너가 6333 포트를 점유하고 있거나, 기존에 128차원 등으로 잘못 생성된 컬렉션 정보가 남아 `Vector dimension error`가 발생하는 경우 아래 명령어로 초기화/재작업할 수 있습니다.

* **옵션 A: 특정 컬렉션만 강제 삭제 (구동 중 컬렉션 초기화)**
  ```bash
  # 128차원 등 이전 데이터 구조가 꼬인 특정 컬렉션만 골라 즉시 삭제
  curl -X DELETE http://localhost:6333/collections/prod_reid_collection
  ```
  *(삭제 후 파이프라인을 재기동하면 올바른 512차원으로 자동 재생성됩니다.)*

* **옵션 B: 전체 컨테이너 및 저장소 초기화 후 재시작**
  ```bash
  # 1. 실행 중인 기존 Qdrant 컨테이너 중지 및 삭제
  docker rm -f $(docker ps -a -q --filter ancestor=qdrant/qdrant)

  # 2. 로컬 저장 폴더가 지저분할 경우 데이터 물리 삭제 (필요한 경우만)
  rm -rf qdrant_storage/

  # 3. 깨끗한 상태로 컨테이너 재실행
  docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant
  ```

### 3.2. 실행 명령어 (edge/ 디렉토리 기준)

> ⚠️ **주의**: Jetson 환경 최적화 옵션인 `--tensorrt` 옵션은 일반 PC 환경에서 에러를 유발할 수 있으므로, **로컬 실행 시에는 해당 플래그를 제외**하고 실행하십시오.

```bash
# 반드시 edge/ 디렉토리로 이동한 후 실행해야 합니다.
cd edge

# 옵션 A. 로컬 비디오 파일을 입력으로 구동 및 모니터링 출력
python main.py --source ../data/16300000.avi --camera-id CAM_01 --display

# 옵션 B. 기본 웹캠(Webcam 0번)을 입력으로 구동 및 모니터링 출력
python main.py --source 0 --camera-id CAM_01 --display

# 옵션 C. RTSP 네트워크 IP 카메라 스트림을 입력으로 구동 및 모니터링 출력
python main.py --source "rtsp://<IP>:<PORT>/stream_path" --camera-id CAM_01 --display
```

### 3.3. 모니터링 단축키 & 제어
`--display` 옵션을 활성화하여 열린 화면 창에서 다음과 같이 인터랙션할 수 있습니다.
- **`q` / `ESC`**: 모니터링 종료 및 파이프라인 안전 소멸
- **`Ctrl + C`** (터미널 창): 실행 중인 에지 서비스 강제 정지 및 자원 반환

### 3.4. Qdrant 수집 데이터 조회 및 확인 방법
파이프라인 실행 중 로컬 Qdrant에 실시간으로 캐싱되어 저장되는 인물 특징 벡터와 메타데이터는 아래의 방법들로 직접 검증하고 조회할 수 있습니다.

#### 3.4.1. 옵션 A: 웹 대시보드(Web UI) 활용 (권장 ⭐️)
인터넷 브라우저를 열고 아래의 주소에 접속하면 저장된 데이터 구조와 메타데이터를 GUI 화면에서 즉시 조회할 수 있습니다.
* URL: **[http://localhost:6333/dashboard](http://localhost:6333/dashboard)**
* **확인 방법**: 좌측 `Collections` 메뉴 ➔ `prod_reid_collection` 선택 ➔ 수집된 포인트(Point)와 메타데이터 페이로드(Payload) 검사.

#### 3.4.2. 옵션 B: 터미널 curl을 이용한 메타데이터(Payload) 조회
터미널 창에서 아래 API를 호출하면 최근 저장된 인물의 세부 메타데이터(입장 시각, 추적 ID, 카메라 ID 등) 상위 10개를 순차적으로 스크롤 조회합니다.
```bash
curl -X POST http://localhost:6333/collections/prod_reid_collection/points/scroll \
     -H 'Content-Type: application/json' \
     -d '{"limit": 10, "with_payload": true, "with_vector": false}'
```

#### 3.4.3. 옵션 C: 컬렉션 통계 및 연결성 확인
컬렉션의 상태, 인덱싱 정보 및 총 저장 개수를 빠르게 확인하고 싶을 때 사용합니다.
```bash
curl http://localhost:6333/collections/prod_reid_collection
```

### 3.5. 실제 백엔드 서버(FastAPI) 전송 검증 방법

에지 파이프라인에서 추출된 Re-ID 특징 벡터 데이터를 백엔드 서버(`http://localhost:8000`)의 `/api/v1/security/detections`로 전송하는 흐름을 검증하는 가이드입니다.

#### 3.5.1. DB 외래 키 제약 충족 (대문자 CAM_01 활용)
백엔드 DB에 탐지 이벤트를 저장하기 전, `detections` 테이블이 참조하는 `cameras` 테이블에 에지에서 사용할 `camera-id`가 미리 인서트되어 있어야 외래 키 위반 에러(`ForeignKeyViolationError`)를 방지할 수 있습니다.

기본 데이터베이스 초기화 스키마(`server/app/db/schema.sql`)에 대문자 **`'CAM_01'`** 카메라 정보가 사전 등록되어 있으므로, 엣지 파이프라인 기동 시 `--camera-id CAM_01` 옵션(기본값)을 사용하면 별도의 등록 명령어 입력 없이 정상 연동됩니다.

만약 다른 임의의 카메라 ID(예: `CAM_02`)를 추가하여 테스트해야 할 경우에는 아래 명령어로 수동 등록할 수 있습니다.
```bash
docker exec -i eyed-postgres psql -U eyed -d eyed -c "INSERT INTO cameras (camera_id, location) VALUES ('CAM_02', 'PS Center sub hall') ON CONFLICT (camera_id) DO NOTHING;"
```

#### 3.5.2. 독립 전송 테스트 스크립트 실행
*성공 시, 로컬 큐 버퍼 사이즈가 `1`에서 `0`으로 비워지며 `Success! Local queue buffer has been emptied (sent to server).` 로그가 출력됩니다.*
```bash
# edge/ 디렉토리 기준
python tools/test_transmission.py
```

#### 3.5.3. 메인 파이프라인 전송 연동 구동
실제 비디오 파일 분석 및 인물 추적 루프 속에서 백엔드 서버로 실시간 데이터를 발송합니다.
```bash
# edge/ 디렉토리 기준
python main.py --source ../data/16300000.avi --camera-id CAM_01 --display --server-url http://localhost:8000
```

---

## 4. 실기기(Jetson) 배포 및 운영 프로세스 (Production Deployment)

실제 임베디드 장비(예: **Jetson Orin Nano**)에 EYE-D 엣지 서비스를 배포하고 프로덕션 수준으로 무중단 운영할 때의 표준 가이드라인입니다.

### 4.1. 모델 하드웨어 가속 최적화 (TensorRT 변환)
Jetson의 GPU 하드웨어를 극대화하기 위해 PyTorch 모델(`.pt`)을 TensorRT Engine(`.engine`)으로 컴파일하여 구동합니다.
* **프로세스**: PyTorch 모델 ➔ ONNX 포맷 변환 ➔ TensorRT 컴파일 (FP16 혹은 INT8 양자화 적용)
* **기동 옵션**: 컴파일이 완료되면 `main.py` 기동 시 `--tensorrt` 플래그를 활성화하여 하드웨어 가속을 켭니다.

### 4.2. 컨테이너 기반 패키징 (Dockerization)
NVIDIA JetPack 전용 베이스 이미지를 활용하여 의존성 충돌을 없애고 도커 이미지화합니다.
* **Dockerfile 예시**:
  ```dockerfile
  FROM nvcr.io/nvidia/l4t-pytorch:r35.2.1-pth2.0-py3
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  COPY edge/ /app
  CMD ["python", "main.py", "--source", "rtsp://...", "--camera-id", "CAM_01", "--tensorrt"]
  ```

### 4.3. 엣지 디바이스 프로비저닝 (환경 설정)
새 Jetson 장비에 리눅스 커널 및 가속 런타임을 연동합니다.
1. **NVIDIA JetPack SDK 설치**: OS(Ubuntu L4T), CUDA, TensorRT 등 설치.
2. **NVIDIA Container Toolkit 설치**: 도커 컨테이너 내부에서 GPU 장치 접근 권한을 획득합니다.
   ```bash
   sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

### 4.4. 무중단 운영 및 업데이트 관리
여러 대의 장비와 카메라를 제어하기 위한 오케스트레이션을 적용합니다.
* **무중단 복구**: `docker-compose` 혹은 경량 쿠버네티스(K3s)를 구성하고 `restart: always` 정책을 주입하여 장비 부팅 시 자동 재가동을 확보합니다.
* **원격 배포 컨트롤**: AWS IoT Greengrass, Azure IoT Edge 등의 에이전트를 구성하여 중앙 서버에서 원격으로 업데이트 및 RTSP 스트림 설정을 동적으로 제어합니다.

### 4.5. 원격 모니터링 및 장애 감지
엣지는 현장에서 과열이나 시스템 락이 자주 발생하므로 주기적으로 메트릭을 수집합니다.
* **수집 주기**: `src/infrastructure/monitoring_agent.py`가 주기적으로 GPU 온도, FPS, RAM 사용량을 감시합니다.
* **대시보드 통합**: 수집된 메트릭을 중앙 Zone of Prometheus/Grafana 관제 시스템으로 송출하여 장애 시 실시간 경고 알림을 작동시킵니다.

---

## 5. RTSP 다채널 스트리밍 모의 테스트 (Mediamtx + FFmpeg)

외부 전송 노드(개발 PC, 로컬 서버 등)에서 일반 비디오 파일(`.mp4` 등)을 실시간 RTSP 네트워크 스트림으로 변환 및 송출하고, 에지 디바이스(`EYE-D` 에지 파이프라인)에서 이를 수신하여 다채널 병렬 처리를 테스트하는 표준 방법론입니다.

### 5.1. Mediamtx (RTSP 미디어 서버) 설정

`Mediamtx`는 Go 언어로 작성된 극도로 가벼운 오픈소스 실시간 미디어 서버입니다.

#### 방법 A. Docker로 실행 (가장 간편함 - 권장)
Docker가 설치된 외부 전송 노드에서 아래 명령어를 입력하여 즉시 구동합니다.
```bash
docker run --rm -it --network=host bluenviron/mediamtx:latest
```
* `--network=host` 옵션을 사용하면 전송 노드의 네트워크 포트를 그대로 활용하므로 별도의 포트 포워딩 설정이 불필요합니다.

#### 방법 B. 바이너리 직접 실행
1. [Mediamtx GitHub Releases](https://github.com/bluenviron/mediamtx/releases)에서 전송 노드 OS에 맞는 압축 파일을 다운로드합니다.
2. 압축을 푼 뒤 생성된 `./mediamtx` (Windows는 `mediamtx.exe`)를 실행합니다.

#### 방화벽 포트 설정
에지가 외부 전송 노드의 RTSP 서버에 접근할 수 있도록 포트를 개방해야 합니다.
* **8554 Port (TCP/UDP)**: RTSP 기본 포트
* *(Ubuntu 기준 UFW 예시)*
  ```bash
  sudo ufw allow 8554/tcp
  sudo ufw allow 8554/udp
  ```

### 5.2. FFmpeg을 이용한 다채널 무한 루프 송출
전송 노드에서 `ffmpeg` 도구를 사용해 3개의 비디오 파일을 각각 `cam01`, `cam02`, `cam03` 이라는 고유 RTSP 경로로 송출합니다.

```bash
# [채널 1 송출] video1.mp4 파일을 cam01 경로로 무한 루프 전송
ffmpeg -re -stream_loop -1 -i video1.mp4 -c copy -f rtsp rtsp://localhost:8554/cam01

# [채널 2 송출] video2.mp4 파일을 cam02 경로로 무한 루프 전송
ffmpeg -re -stream_loop -1 -i video2.mp4 -c copy -f rtsp rtsp://localhost:8554/cam02

# [채널 3 송출] video3.mp4 파일을 cam03 경로로 무한 루프 전송
ffmpeg -re -stream_loop -1 -i video3.mp4 -c copy -f rtsp rtsp://localhost:8554/cam03
```
* **옵션 설명**:
  * `-re`: 비디오 프레임 레이트에 맞추어 실시간 속도로 비디오를 스트리밍하는 필수 옵션입니다.
  * `-stream_loop -1`: 비디오 종료 시 무한 반복 스트리밍되도록 지정합니다.
  * `-c copy`: 원본 코덱 데이터를 디코딩/인코딩하지 않고 복사해 송출하여 CPU 부하를 거의 발생시키지 않는 최적화 옵션입니다.

### 5.3. 에지 노드(수신 측) 정상 수신 검증
에지 기기에서 실제 스트림이 도달하는지 `ffplay`를 사용해 사전 점검할 수 있습니다.
```bash
ffplay rtsp://<전송노드_IP>:8554/cam01
```

### 5.4. 에지 AI 파이프라인 연동 (`main.py` 구동 예시)
수신이 확인되면 에지 장비에서 수신 주소 값을 넣어 파이프라인을 기동합니다.
```bash
python edge/main.py --source rtsp://<전송노드_IP>:8554/cam01 --camera-id CAM_01
```
*(추후 다채널 병렬 처리가 `main.py`에 적용 완료되면, 여러 개의 RTSP 경로를 딕셔너리로 묶어 단일 명령어 구동을 지원할 예정입니다.)*

