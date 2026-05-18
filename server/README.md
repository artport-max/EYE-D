# EYE-D 백엔드 학습 프로젝트

이 폴더는 본인이 맡은 **데이터 파이프라인/백엔드 부분**을 처음부터 단계적으로 만들어가는 작업 공간입니다.

## 시작 방법

상위 폴더의 [`백엔드_학습_가이드.md`](../백엔드_학습_가이드.md) 파일을 처음부터 차례대로 따라가세요. 각 단계 끝에 "체크포인트"가 있어 동작을 확인하고 다음 단계로 진행할 수 있습니다.

## 폴더 구조 (가이드를 따라가며 채워질 모습)

```
backend_EYE-D/PS Center/
├── README.md              # 이 파일
├── requirements.txt       # 파이썬 패키지 목록 (제공됨)
├── docker-compose.yml     # PostgreSQL + pgvector (제공됨)
├── .env.example           # 환경변수 템플릿 (제공됨)
├── .gitignore             # 깃 제외 목록 (제공됨)
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI 진입점
│   ├── schemas/
│   │   └── detection.py   # Pydantic 스키마
│   ├── db/
│   │   ├── conn.py        # DB 연결 풀
│   │   └── schema.sql     # 테이블 정의
│   ├── routers/
│   │   ├── security.py    # EYE-D 본 용도 (/api/v1/security/*)
│   │   └── art.py         # arttrace 확장 슬롯 (빈 라우터)
│   └── services/
│       ├── matcher.py     # 코사인 유사도 매칭
│       └── token_governor.py  # AI 토큰 관리 미들웨어
└── tools/
    └── mock_sender.py     # 엣지를 흉내내는 송신 스크립트
```

## 환경 변수

`.env.example`을 복사해 `.env`로 만들고 본인 환경에 맞게 수정합니다.

```
copy .env.example .env
```
