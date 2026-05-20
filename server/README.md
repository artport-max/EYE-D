# EYE-D 백엔드 (PS Center 코어)

이 폴더는 **데이터 파이프라인/백엔드 부분** 작업 공간입니다.
이전 이름인 `../../backend_kote/` 의 역할을 모두 이쪽으로 옮겼습니다.

- 시스템 코드네임: **EYE-D**
- 운영자 제품명: **PS Center**
- DB: `eyed/eyed_dev_pw/eyed` (2026-05-19 통일)

## 폴더 구조

```
EYE-D/server/
├── README.md              # 이 파일
├── requirements.txt
├── docker-compose.yml     # PostgreSQL + pgvector
├── .env.example
├── app/
│   ├── main.py            # FastAPI 진입점
│   ├── schemas/detection.py
│   ├── db/
│   │   ├── conn.py
│   │   ├── schema.sql     # 초기 테이블 정의 (cameras, persons, detections, art_events)
│   │   └── migrations/    # 증분 ALTER (예: 2026-05-19_retail.sql)
│   ├── routers/
│   │   ├── security.py    # /api/v1/security/* (탐지·동선·알림)
│   │   ├── retail.py      # /api/v1/retail/*   (VIP/단골·체류분석) ← 2026-05-19 추가
│   │   └── art.py         # /api/v1/art/*      (arttrace, Phase B)
│   └── services/
│       ├── matcher.py             # Re-ID 코사인 매칭
│       ├── customer_classifier.py # VIP/단골 자동 분류  ← 2026-05-19 추가
│       ├── dwell_analyzer.py      # 체류·동선 특징 분석 ← 2026-05-19 추가
│       └── token_governor.py
├── docs/
│   └── feature_analysis.md  # 고객 분류·체류 분석 설계 노트 ← 2026-05-19 추가
└── tools/
    └── mock_sender.py
```

## 환경 변수

```
copy .env.example .env
```

## 시작 방법 (개발자 환경)

```
docker compose up -d                            # Postgres 기동 (schema.sql 자동 초기화)
python -m venv .venv && .venv\Scripts\activate  # (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# DB 마이그레이션 적용 (최초 1회만 실행. DB 볼륨 삭제 후 재기동 시에도 1회 실행 필요)
# - Windows (PowerShell):
Get-Content .\app\db\migrations\2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
# - Linux / macOS (Bash):
# cat app/db/migrations/2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed

uvicorn app.main:app --reload
```
