# EYE-D — Server 코드 분석 및 테스트 가이드

> 작성일: 2026-05-13  
> 대상: `server/` 폴더 전체  
> 분석 기준: git pull로 수신된 초기 구현 코드

---

## 1. 현재 구현 현황

### 파일 구조

```
server/
├── .env.example             # 환경변수 템플릿
├── README.md
├── docker-compose.yml       # PostgreSQL + pgvector
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 진입점 (lifespan, /health, /admin/tokens)
│   ├── db/
│   │   ├── conn.py          # asyncpg 연결 풀 (init/close/get)
│   │   └── schema.sql       # 테이블 정의 (cameras, persons, detections, art_events)
│   ├── routers/
│   │   ├── security.py      # POST /detections, GET /persons/{id}/track, WS /ws/alerts
│   │   └── art.py           # 501 stub (arttrace 슬롯)
│   ├── schemas/
│   │   └── detection.py     # DetectionIn / DetectionOut (Pydantic)
│   └── services/
│       ├── matcher.py       # find_or_create_global_id (pgvector 코사인 거리)
│       └── token_governor.py # AI 토큰 예산 관리 싱글턴
└── tools/
    └── mock_sender.py       # 엣지 시뮬레이터 (5명 × 3라운드)
```

### 클래스 다이어그램 (Class Diagram)

```mermaid
classDiagram
    %% Pydantic Schemas
    class DetectionIn {
        +String camera_id
        +String tracklet_id
        +List~Float~ embedding_identity
        +DateTime timestamp
        +List~Float~ bbox
        +String event_type
        +List~List~Float~~ pose_keypoints
        +String action_label
        +Float dwell_seconds
        +Dict appearance_attrs
        +Dict scene_context
    }

    class DetectionOut {
        +Int detection_id
        +Int global_id
        +Bool matched
        +Float similarity
    }

    %% Token Governor Services
    class TokenUsage {
        <<dataclass>>
        +Int daily_used
        +Float day_started_at
        +List~Dict~ last_traces
    }

    class TokenBudgetExceeded {
        <<Exception>>
    }

    class TokenGovernor {
        +TokenUsage usage
        +Int daily_budget
        +Int per_request_max
        - _rotate_day_if_needed()
        + request(agent, tokens_estimate, meta) String
        + commit(trace_id, actual_tokens)
        + stats() Dict
    }

    TokenGovernor --> TokenUsage : manages
    TokenGovernor ..> TokenBudgetExceeded : throws
```

### 컴포넌트 다이어그램 (Component Diagram)

서버 내부의 논리적 모듈 구조와 의존성을 보여줍니다.

```mermaid
graph TD
    subgraph "FastAPI Server (app/)"
        Main[main.py<br/>Lifespan & Health]
        
        subgraph "Routers"
            SecurityRouter[routers/security.py<br/>Detection & Alerts]
            ArtRouter[routers/art.py<br/>ArtTrace Stub]
        end
        
        subgraph "Services"
            Matcher[services/matcher.py<br/>Re-ID Logic]
            TokenGov[services/token_governor.py<br/>AI Token Manager]
        end
        
        subgraph "Database Layer"
            DBConn[db/conn.py<br/>asyncpg Pool]
        end
        
        subgraph "Schemas"
            DetectionSchema[schemas/detection.py<br/>Pydantic Models]
        end
    end

    Main --> SecurityRouter
    Main --> ArtRouter
    Main --> DBConn
    
    SecurityRouter --> DetectionSchema
    SecurityRouter --> Matcher
    SecurityRouter --> DBConn
    
    ArtRouter --> TokenGov
    Matcher --> DBConn
```

**컴포넌트별 주요 역할:**
*   **Main (`main.py`)**: FastAPI 애플리케이션의 진입점입니다. 서버가 켜지고 꺼질 때 DB 연결 풀을 생성/종료(Lifespan)하며, 전역 예외 처리 및 `/health` 라우터를 설정합니다.
*   **SecurityRouter (`routers/security.py`)**: 엣지에서 들어오는 탐지 데이터 수신, 특정 인물의 동선 조회, 웹 대시보드로의 WebSocket 알림 전송 등 **핵심 비즈니스 로직의 API 엔드포인트**를 담당합니다.
*   **ArtRouter (`routers/art.py`)**: 향후 추가될 확장 기능(예: 예술 작품 반응형 알림 등)을 위한 Stub(빈 껍데기) 엔드포인트입니다.
*   **Matcher (`services/matcher.py`)**: 수신된 탐지 데이터의 OSNet 벡터(Embedding)를 DB에 저장된 기존 벡터들과 코사인 거리 기반으로 비교하여, **동일 인물 여부(Re-ID, `global_id` 부여)**를 판별하는 핵심 알고리즘 계층입니다.
*   **TokenGov (`services/token_governor.py`)**: LLM 등 외부 AI 서비스 호출 시 발생할 수 있는 토큰 비용을 추적하고 제한하는 메모리 기반 예산 관리기입니다.
*   **DBConn (`db/conn.py`)**: `asyncpg`를 활용하여 비동기 데이터베이스 커넥션 풀을 초기화하고 유지보수합니다.
*   **DetectionSchema (`schemas/detection.py`)**: Pydantic을 활용하여 엣지로부터 수신하는 JSON 데이터(`DetectionIn`)와 응답 데이터(`DetectionOut`)의 타입 및 필수값을 **엄격하게 검증**합니다.

### 배포 다이어그램 (Deployment Diagram)

물리적/가상화된 노드 간의 통신과 배포 구조를 보여줍니다.

```mermaid
flowchart TB
    subgraph "Edge Device (Jetson Nano)"
        EdgePipeline["Edge Pipeline<br/>(OSNet / Re-ID)"]
        MockSender["tools/mock_sender.py<br/>(Simulator)"]
    end

    subgraph "Client (Admin/Security)"
        Dashboard["Web Dashboard<br/>(Browser)"]
    end

    subgraph "Backend Server Node (Ubuntu / VM)"
        FastAPI["FastAPI App<br/>(Uvicorn)"]
        
        subgraph "Docker Engine"
            PostgresContainer[("PostgreSQL 15<br/>+ pgvector<br/>(Port: 5433)")]
        end
    end

    EdgePipeline -- "HTTP POST<br/>/detections" --> FastAPI
    MockSender -. "HTTP POST<br/>/detections" .-> FastAPI
    Dashboard -- "WebSocket<br/>/ws/alerts" --> FastAPI
    FastAPI -- "TCP<br/>asyncpg" --> PostgresContainer
```

---

## 2. 구현된 엔드포인트

| 메서드 | 경로 | 설명 | 상태 |
|--------|------|------|------|
| GET | `/health` | 서버 + DB 헬스체크 | ✅ 완성 |
| GET | `/admin/tokens` | 토큰 사용 통계 | ✅ 완성 |
| POST | `/api/v1/security/detections` | 탐지 이벤트 수신 + 매칭 + 저장 | ✅ 완성 |
| GET | `/api/v1/security/persons/{id}/track` | 인물 동선 조회 | ✅ 완성 |
| WS | `/api/v1/security/ws/alerts` | 실시간 침입 알림 구독 | ✅ 완성 |
| POST | `/api/v1/art/interpretations` | arttrace 슬롯 | 501 stub |
| POST | `/api/v1/art/generations/text` | arttrace 슬롯 | 501 stub |
| POST | `/api/v1/art/generations/audio` | arttrace 슬롯 | 501 stub |

---

## 3. POST /detections 데이터 흐름 (엣지 연동)

엣지(Jetson)로부터 탐지 이벤트(JSON)를 수신했을 때, 서버가 수행하는 핵심 역할은 다음과 같습니다.

1. **데이터 검증 (Validation):**
   - 수신된 데이터가 Pydantic 스키마(`DetectionIn`) 규격에 맞는지 확인합니다. (누락된 필수 값이나 잘못된 타입이 있으면 즉시 거절)
2. **동일인 재식별 (Re-ID Matching):**
   - 엣지에서 보낸 인물 특징 벡터(OSNet Embedding)를 기존 데이터베이스에 저장된 최근 24시간 내 벡터들과 코사인 유사도(`<=>`)로 비교합니다.
   - 설정된 임계값(유사도 0.85 이상)을 넘는 가장 가까운 인물이 있다면 **기존 인물(global_id)**로 매칭합니다.
   - 없다면 **새로운 인물**로 판단하여 DB에 새로 등록하고 새로운 `global_id`를 부여합니다.
3. **데이터 저장 (DB Transaction):**
   - 탐지 위치(`bbox`), 시간(`timestamp`), 벡터, 카메라 ID 등 모든 정보를 `detections` 테이블에 저장합니다.
   - 기존 인물로 판명된 경우 `persons` 테이블의 마지막 목격 시간(`last_seen_at`)을 갱신합니다.
4. **실시간 알림 전파 (WebSocket Broadcast):**
   - 만약 수신된 이벤트가 단순 탐지(detection)가 아닌 **"침입(intrusion)"**이라면, 웹 대시보드와 연결된 모든 WebSocket 클라이언트에게 즉시 경고 데이터를 Push 합니다.
5. **결과 반환:**
   - 최종적으로 부여된 `global_id`, 매칭 여부, 유사도 값을 엣지 장비로 다시 응답합니다.

```text
[엣지 또는 mock_sender]
    │ HTTP POST JSON
    ▼
[DetectionIn 검증]  ← Pydantic
    │ 실패 시: 422 반환 (DB 미접근)
    ▼
[asyncpg 연결 풀에서 connection 획득]
    │
    ▼
[트랜잭션 시작]
    ├─ ① find_or_create_global_id()   ← matcher.py
    │    - 24h 내 detections에서 가장 가까운 벡터 검색 (pgvector <=> 연산자)
    │    - 코사인 거리 < 0.15 (유사도 > 0.85) → 기존 global_id 반환
    │    - 아니면 → persons에 새 레코드 INSERT, 새 global_id 반환
    │
    ├─ ② detections INSERT
    │    - embedding_identity::vector 저장
    │    - is_intrusion = (event_type == "intrusion")
    │
    └─ ③ persons.last_seen_at UPDATE
    │
[트랜잭션 커밋]
    │
    ▼
[intrusion이면 broadcast_intrusion()]  ← 트랜잭션 밖 (DB 커밋 후)
    └─ 연결된 모든 WS 클라이언트에 JSON 푸시
    │
    ▼
[DetectionOut 반환]
    {detection_id, global_id, matched, similarity}
```

### 시퀀스 다이어그램 (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor Edge as 엣지 장비 (Jetson)
    participant FastAPI as FastAPI 라우터
    participant Schema as Pydantic 검증
    participant Matcher as Matcher 서비스
    participant DB as PostgreSQL DB
    participant WS as WebSocket 클라이언트

    Edge->>FastAPI: HTTP POST /api/v1/security/detections (JSON)
    FastAPI->>Schema: 데이터 규격 검증 (DetectionIn)
    
    alt 검증 실패
        Schema-->>FastAPI: Validation Error
        FastAPI-->>Edge: HTTP 422 Unprocessable Entity
    else 검증 성공
        Schema-->>FastAPI: Validated Data
        FastAPI->>DB: 트랜잭션 시작 (BEGIN)
        FastAPI->>Matcher: find_or_create_global_id()
        Matcher->>DB: 최근 24시간 벡터 코사인 유사도 검색
        
        alt 유사도 > 0.85 (기존 인물)
            DB-->>Matcher: 기존 레코드 반환
            Matcher-->>FastAPI: 기존 global_id 반환
        else 매칭 없음 (새로운 인물)
            Matcher->>DB: persons 테이블에 새 레코드 INSERT
            DB-->>Matcher: 새 레코드 반환
            Matcher-->>FastAPI: 신규 global_id 반환
        end
        
        FastAPI->>DB: detections 테이블에 데이터 INSERT
        FastAPI->>DB: persons 테이블 last_seen_at UPDATE
        FastAPI->>DB: 트랜잭션 커밋 (COMMIT)
        
        opt event_type == "intrusion"
            FastAPI->>WS: 침입 경고 실시간 푸시 (Broadcast)
        end
        
        FastAPI-->>Edge: HTTP 200 OK (DetectionOut 반환)
    end
```

---

## 4. 핵심 설계 요소

### DetectionIn 스키마

```python
# 필수 필드
camera_id: str              # "CAM_01"
tracklet_id: str            # 엣지 내 임시 추적 ID
embedding_identity: list[float]  # OSNet 512차원 벡터
timestamp: datetime
bbox: list[float]           # [x1, y1, x2, y2]
event_type: str             # "detection" | "intrusion"

# 옵션 (arttrace 슬롯, 현재 null 허용)
pose_keypoints: Optional[list[list[float]]]
action_label: Optional[str]
dwell_seconds: Optional[float]
appearance_attrs: Optional[dict]
scene_context: Optional[dict]
```

### 환경변수 (.env)

```ini
DATABASE_URL=postgresql://kote:kote_dev_pw@localhost:5432/kote
APP_HOST=127.0.0.1
APP_PORT=8000
REID_SIMILARITY_THRESHOLD=0.85   # 동일인 판정 임계값
EMBEDDING_DIM=512                 # OSNet 벡터 차원
DAILY_TOKEN_BUDGET=100000         # AI 일일 토큰 한도
PER_REQUEST_MAX_TOKENS=2000       # 1회 호출당 최대 토큰
```

---

## 5. ⚠️ 발견된 버그

### matcher.py — Dead Code (도달 불가능한 코드)

```python
# matcher.py 40~45번 줄
new_id = await conn.fetchval(
    "INSERT INTO persons DEFAULT VALUES RETURNING global_id"
)
return int(new_id), None, False     # ← 여기서 이미 return
if row and row["distance"] is not None and ...:  # ← 절대 실행 안 됨!
    return int(row["global_id"]), 1.0 - float(row["distance"]), True
```

**영향**: 기능 동작 자체에는 문제 없음 (위의 올바른 return이 먼저 실행됨).  
**수정 방법**: 44~45번 줄 삭제.

---

## 6. 테스트 방법

### 방법 A: 실제 서버 실행 (통합 테스트)

```bash
# 1. 환경 설정
cd /home/torious/projects/tmp/EYE-D/server
cp .env.example .env

# 2. DB 실행
docker-compose up -d

# 3. Python 패키지 설치
pip install -r requirements.txt

# 4. 서버 실행
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 5. 헬스체크
curl http://127.0.0.1:8000/health

# 6. 엣지 시뮬레이션 (새 터미널)
python tools/mock_sender.py
```

### 방법 B: pytest 단위 테스트 (DB 없이)

> `tests/` 디렉토리가 비어있음 → 테스트 작성 필요.

**테스트 대상 우선순위**:

| 우선순위 | 파일 | 테스트 내용 |
|---------|------|-----------|
| 🔴 HIGH | `schemas/detection.py` | DetectionIn 필수/옵션 필드 검증 |
| 🔴 HIGH | `services/matcher.py` | 매칭 로직 (임계값 분기, 새 person 생성) |
| 🟡 MED | `routers/security.py` | POST 응답 구조, 404 처리 |
| 🟡 MED | `app/main.py` | /health, /admin/tokens 응답 |

### Swagger UI 수동 테스트

서버 실행 후: `http://127.0.0.1:8000/docs`

### WebSocket 수동 테스트 (브라우저 콘솔)

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/api/v1/security/ws/alerts");
ws.onopen = () => console.log("WS connected");
ws.onmessage = (e) => console.log("ALERT:", e.data);
```

---

## 7. 다음 단계 제안

| # | 작업 | 설명 |
|---|------|------|
| 1 | **버그 수정** | `matcher.py` dead code 제거 |
| 2 | **테스트 작성** | `tests/` 하네스 구축 (edge와 동일 방식) |
| 3 | **서버 실행** | Docker + uvicorn으로 통합 검증 |
| 4 | **edge 연동** | edge의 `ServerSender` 구현 (Phase 3)하여 실제 연동 |
