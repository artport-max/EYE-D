# EYE-D Edge — 테스트 실행 가이드

> 환경: `conda activate cv_poc` → `cd edge/`  
> 설정 파일: `edge/pytest.ini`

---

## 사전 준비

```bash
# 1. conda 환경 활성화
conda activate cv_poc

# 2. edge/ 디렉토리로 이동 (반드시 이 위치에서 실행)
cd <PROJECT_ROOT_DIR>/edge

# 3. pytest 미설치 시
pip install pytest
```

---

## 기본 실행

```bash
# 전체 단위 테스트 실행
python -m pytest tests/unit/test_pipeline_runner.py

# 전체 tests/ 하위 모든 테스트 실행
python -m pytest
```

---

## 선택적 실행

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

---

## 출력 옵션

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

---

## 커버리지 측정 (선택)

```bash
# pytest-cov 설치
pip install pytest-cov

# 커버리지 포함 실행
python -m pytest --cov=src --cov-report=term-missing
```

---

## 실시간 인터랙티브 비주얼 데모 테스트 (tools/visual_demo.py)

단위 테스트를 넘어, 실제 영상 혹은 자율 합성된 가상 환경 하에서 실시간 엣지 파이프라인 보정 효과를 눈으로 직접 보며 인터랙티브하게 검증할 수 있는 통합 시각화 데모 도구입니다.

### 1. 실행 명령

반드시 `conda activate cv_poc` 활성화 및 `edge/` 디렉토리로 이동한 후 기동하십시오.

```bash
# 옵션 A. 가상 악조건(저조도 야간, 역광 루프) 자율 시뮬레이션 데모 가동 (추천)
python tools/visual_demo.py

# 옵션 B. 실제 소유한 로컬 비디오 파일(.mp4 등)을 입력으로 주어 데모 가동
python tools/visual_demo.py --video <테스트비디오경로>
```

### 2. 키보드 인터랙티브 조작 보드

시각화 윈도우 창이 떠 있는 상태에서 아래의 단축키를 눌러 실시간으로 필터 적용 전후를 사이드-바이-사이드로 비교할 수 있습니다.

| 단축키 | 작동 필터 | 튜닝 보정 효과 설명 |
|:---:|---|---|
| **`N`** | **야간 저조도 모드 (Night)** | 감마 1.6 보정 LUT 테이블을 적용하여, 저조도 속 어두운 피사체를 화사하고 뚜렷하게 밝힙니다. |
| **`B`** | **역광 보정 모드 (Backlight)** | 명암 편차가 심해 어둡게 타버린 인물 그늘 영역에 CLAHE를 가중 적용해 윤곽을 복구합니다. |
| **`S`** | **저해상도 ROI 선명화 (Sharpen)** | 우측 하단 돋보기 창에 언샤프 마스킹 선명도를 적용해, 인물 크롭 텍스처를 34% 이상 선명히 복원합니다. |
| **`Q` / `ESC`** | **데모 정지 및 종료** | 실시간 데모의 윈도우를 안전하게 닫고 모든 하드웨어 자원을 해제합니다. |

---

## 테스트 파일 위치 구조

```
edge/
├── pytest.ini                              # 설정 (testpaths, pythonpath)
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

## 현재 테스트 현황

| 파일 | 테스트 수 | 마지막 결과 |
|------|----------|------------|
| `test_null_objects.py` | 20개 | ✅ 20 passed |
| `test_pipeline_runner.py` | 21개 | ✅ 21 passed |
| `test_phase2_resilience.py` | 4개 | ✅ 4 passed |
| `test_phase3_multistream.py` | 1개 | ✅ 1 passed |
| `test_phase3_harsh_conditions.py` | 3개 | ✅ 3 passed |
| `test_e2e_pipeline.py` | 2개 | ✅ 2 passed |
| **합계** | **51개** | ✅ **51 passed** |

---

## pytest.ini 설정 내용

```ini
[pytest]
testpaths = tests        # 테스트 루트
pythonpath = .           # src/ 임포트 경로 설정
addopts = -v --tb=short  # 기본 출력 옵션
```

> ⚠️ 반드시 `edge/` 디렉토리에서 실행해야 `pytest.ini`가 인식됩니다.
