# EYE-D 팀 협업 워크플로우 가이드

**대상**: 3인 연구 협업팀 (Linux 환경 팀장님 + Windows 환경 무림 + 기타)
**갱신**: 2026-05-20
**배경**: 라인엔딩(CRLF↔LF) 충돌 사고를 계기로 정립.

---

## 1. 한 줄 원칙

> **항상 `main` 에서 시작 → feature 브랜치에서 작업 → PR → 머지 후 로컬 정리.**
> **`main` 에는 직접 푸시하지 않는다** (docs/긴급 hotfix 예외).

---

## 2. 일일 작업 순서

### 2.1 작업 시작 — 매번 반드시 실행

```powershell
# 위치: EYE-D/
cd "C:\Users\murim\OneDrive\문서\Claude\Projects\엣지 게이트웨이 기반 지능형 침입 탐지 및 인물 재식별(Re-ID) 시스템\EYE-D"

git checkout main          # main 으로 전환
git pull                   # 팀장님 변경 받아오기
git checkout -b feature/<주제>    # 새 feature 브랜치 만들기 (예: feature/retail-ws-test)
```

> **브랜치 이름 규칙**: `feature/<짧은-주제>` 또는 `fix/<짧은-주제>`, `docs/<짧은-주제>`. 예: `feature/vip-realtime-alert`, `fix/dwell-zero-duration`, `docs/api-contract`.

### 2.2 작업 중 — 작은 단위로 자주 커밋

```powershell
git status                 # 자주 확인 (1시간에 한 번이라도)
git diff <파일>             # 무엇을 바꿨는지 확인
git add <특정 파일들>        # 의도한 것만 명시적으로 스테이징
git commit -m "fix(retail): handle null dwell when visit ends immediately"
```

**커밋 메시지 컨벤션** (현재 팀 사용 형식 그대로):
- `feat(area): ...` — 신규 기능
- `fix(area): ...` — 버그 수정
- `refactor(area): ...` — 동작 동일, 구조 개선
- `docs(area): ...` — 문서만
- `chore: ...` — 빌드/설정/잡일

**area 예시**: `retail`, `security`, `edge`, `db`, `matcher`, `frontend`.

### 2.3 push 와 PR

```powershell
git push -u origin feature/<주제>   # 첫 push 만 -u (이후엔 git push 단독)
```

GitHub 에서 PR 생성 → 팀장님 리뷰 → 머지.

### 2.4 PR 머지 후 — 로컬 정리

```powershell
git checkout main
git pull                    # 머지된 main 가져오기
git branch -d feature/<주제>  # 로컬 feature 브랜치 삭제
git remote prune origin     # origin 의 사라진 브랜치 참조 정리 (선택)
```

---

## 3. 크로스플랫폼 주의사항 (Linux 팀장 ↔ Windows 무림)

### 3.1 라인엔딩 — `.gitattributes` 가 알아서 처리

이미 EYE-D 루트에 `.gitattributes` 가 있으므로 신경 안 써도 됩니다. 단, 새 컴퓨터/새 클론 시:

```powershell
git config core.autocrlf input    # Windows 에서 한 번
```

(Linux/Mac 은 기본값이 적절해서 별도 설정 불필요.)

**증상**: 손 안 댄 파일이 modified 로 잡히면 라인엔딩 의심. 확인 명령:
```powershell
git diff -w --stat <파일>     # 공백 무시 시에도 diff 가 있으면 진짜 변경
```

### 3.2 파일 경로

- 코드에서 경로는 항상 **forward slash** 사용 또는 `pathlib.Path` 활용. 예:
  - 좋음: `Path(__file__).resolve().parent / ".env"`
  - 좋음: `"server/app/main.py"` (Python, 양쪽 OS 동작)
  - 나쁨: `"server\\app\\main.py"` (Linux 에서 깨짐)

### 3.3 셸 명령어

문서나 스크립트에 명령을 적을 때는 **양쪽 모두 제공**:

| 작업 | Windows (PowerShell) | Linux/Mac (Bash) |
|---|---|---|
| 파일 보기 | `Get-Content file.txt` | `cat file.txt` |
| 파일 검색 | `Select-String "term" file` | `grep "term" file` |
| 디렉토리 변경 | `cd "경로"` (공백 시 따옴표) | `cd "경로"` |
| 환경변수 set | `$env:VAR = "값"` | `export VAR="값"` |
| 환경변수 보기 | `$env:VAR` | `echo $VAR` |
| 가상환경 활성화 | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| 파이프 + docker exec | `Get-Content file.sql \| docker exec -i ...` | `cat file.sql \| docker exec -i ...` |

스크립트 작성 시:
- Linux 양쪽 모두 돌릴 거면 → Python 스크립트로 통일
- Windows 전용 → `.ps1` 또는 `.bat` (확장자 명시, .gitattributes 가 CRLF 유지)
- Linux 전용 → `.sh` (LF 유지)

### 3.4 환경변수 / 포트

EYE-D 백엔드 핵심 설정:
- Postgres 호스트 노출 포트: **5433** (`localhost:5433`)
- Postgres 컨테이너 내부 포트: 5432
- API 서버: 8000
- `.env` 는 `EYE-D/server/.env` 에 위치. `load_dotenv()` 는 절대경로로 로드 중이라 실행 위치 무관.

---

## 4. 자주 발생하는 상황과 대처

### 4.1 모르는 modified 파일이 git status 에 잡힘

1. `git diff <파일>` 로 내용 확인
2. 라인엔딩만 다른지 `diff -w --stat` 로 재확인
3. 본인이 안 한 변경이면 **커밋하지 말 것**. `git log -1 --all <파일>` 로 최근 변경 추적, 팀장님과 확인.
4. 정말 본인이 한 작업이면 별도 의미 있는 커밋으로 분리

### 4.2 push 거부 (`rejected — non-fast-forward`)

팀장님이 같은 브랜치에 먼저 push 한 경우:
```powershell
git pull --rebase    # 본인 커밋을 팀장님 커밋 위로 다시 쌓기
# 충돌 발생 시 충돌 해결 후 git rebase --continue
git push
```

### 4.3 잘못된 파일 staged 됐을 때

```powershell
git restore --staged <파일>    # staging 만 풀고 working tree 변경은 유지
```

### 4.4 어떤 작업 도중에 다른 일을 급하게 해야 할 때

```powershell
git stash push -m "WIP: <설명>"     # 현재 변경 보관
# ... 다른 일 ...
git stash list
git stash pop                       # 보관한 변경 복원
```

### 4.5 마지막 커밋 메시지 수정

```powershell
git commit --amend -m "새 메시지"     # 마지막 커밋 메시지만 변경
# 이미 push 한 후라면 안전 차원에서 amend 후 push 는 force-with-lease 사용
git push --force-with-lease
```

> **주의**: 다른 사람도 받은 커밋은 amend 하지 말 것. 본인 feature 브랜치에서만 사용.

---

## 5. EYE-D 특화 체크리스트

### 5.1 서버 기동 (Windows)

```powershell
# 위치: EYE-D/server
cd "...\EYE-D\server"
docker compose up -d                            # Postgres 기동
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt                 # 최초 또는 deps 변경 시
Get-Content .\app\db\migrations\2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
uvicorn app.main:app --reload
```

### 5.2 서버 기동 (Linux/Mac)

```bash
cd EYE-D/server
docker compose up -d
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cat app/db/migrations/2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
uvicorn app.main:app --reload
```

### 5.3 검증 한 줄

```
curl http://127.0.0.1:8000/health
# {"status":"ok","db":1}
```

### 5.4 mock 데이터 전송

```
python tools/mock_sender.py
```

---

## 6. 트러블슈팅 체크리스트 — 문제 발생 시 위에서부터 확인

1. **컨테이너 살아있나?** → `docker ps` 에 `eyed-postgres` 가 `Up` 인지
2. **DB 응답하나?** → `docker exec eyed-postgres pg_isready -U eyed`
3. **포트 충돌?** → 호스트 5433 / 8000 다른 프로세스 점유 여부
4. **마이그레이션 적용됐나?** → `docker exec -it eyed-postgres psql -U eyed -d eyed -c "\d persons"` 에 `customer_tier`, `visit_count` 컬럼 있는지
5. **`.env` 로드됐나?** → uvicorn 시작 직후 `[startup] DB pool ready` 메시지 확인
6. **라인엔딩 충돌?** → `git diff -w --stat` 로 진짜 변경 vs CRLF/LF 차이 구분
7. **본인 안 만든 변경?** → 커밋 전 `git diff` 로 출처 확인, 팀장님 작업 가능성 의심

---

## 7. 참고

- 저장소: `https://github.com/artport-max/EYE-D` (fork) → upstream `MarcusBae/EYE-D`
- 검증 보고서 예시: `server/docs/verification_2026-05-20.md`
- 백엔드 README: `server/README.md`
- 본 문서는 새 협업 패턴 도입 시 함께 업데이트할 것.
