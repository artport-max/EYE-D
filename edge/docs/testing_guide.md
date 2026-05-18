# EYE-D Edge — 테스트 실행 가이드

> 환경: `conda activate cv_poc` → `cd edge/`  
> 설정 파일: `edge/pytest.ini`

---

## 사전 준비

```bash
# 1. conda 환경 활성화
conda activate cv_poc

# 2. edge/ 디렉토리로 이동 (반드시 이 위치에서 실행)
cd /home/torious/projects/tmp/EYE-D/edge

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
        └── test_pipeline_runner.py         # PipelineRunner 단위 테스트 (21개)
```

---

## 현재 테스트 현황

| 파일 | 테스트 수 | 마지막 결과 |
|------|----------|------------|
| `test_pipeline_runner.py` | 21개 | ✅ 21 passed (0.43s) |

---

## pytest.ini 설정 내용

```ini
[pytest]
testpaths = tests        # 테스트 루트
pythonpath = .           # src/ 임포트 경로 설정
addopts = -v --tb=short  # 기본 출력 옵션
```

> ⚠️ 반드시 `edge/` 디렉토리에서 실행해야 `pytest.ini`가 인식됩니다.
