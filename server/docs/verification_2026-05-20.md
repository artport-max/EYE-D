# EYE-D Backend 데이터 동작 검증 보고

**일시**: 2026-05-20
**담당**: 무림 (백엔드/데이터 파이프라인)
**대상 커밋**: `f672f03` — fix(db): align Postgres port to 5433
**브랜치**: `feature/eyed-retail-vip-dwell` (origin/artport-max 푸시 완료)

---

## 1. 결론

**서버·DB·Re-ID 매칭·고객 분류·통계 API 까지 end-to-end 정상 동작**. 팀장님 OSNet 연동 전까지 mock 데이터 기반 백엔드 단독 검증 통과.

| 영역 | 상태 | 근거 |
|---|---|---|
| 서버 기동 | OK | `/health` → 200, `db:1` |
| DB 마이그레이션 | OK | persons(+6 컬럼), person_visits, zone_visits, zones 모두 생성 |
| Detection 수신 | OK | mock_sender 30건 POST 전부 성공 |
| Re-ID 매칭 | OK | Round 2~6 모두 `matched=True` (100%) |
| 자동 분류 (regular 승격) | OK | 5명 전원 `visit_count=6` 도달 시 `tier=regular` 승격 |
| 통계 집계 | OK | `/stats/hourly` 시간대별 visits·unique_visitors 정상 |
| WebSocket 알림 | (미검증) | 라운드 5 부근 `regular_visit` 알림 발생 예정 — 다음 검증에서 ws 클라이언트 붙여 확인 예정 |

---

## 2. 이번 세션 수정 내역 (배경)

uvicorn 기동 시 `ConnectionRefusedError [WinError 1225]` + mock_sender 500 에러 두 증상이 같은 root cause(호스트 Postgres 포트 5433 노출인데 코드/문서 기본값 5432) 에서 비롯됨. 4 개 파일 동시 정렬:

- `app/db/conn.py` — 기본 DSN fallback `5432 → 5433`
- `app/main.py` — `load_dotenv()` 절대경로화 (CWD 무관하게 `.env` 로드 보장)
- `server/README.md` — psql 명령을 `docker exec` 파이프라인으로 교체 (호스트 psql 없어도 동작)
- `app/db/migrations/2026-05-19_retail.sql` — 헤더 주석의 적용 방법 갱신

---

## 3. 검증 절차 및 결과

### 3.1 서버 health

```
GET /health → 200 {"status":"ok","db":1}
```

### 3.2 mock_sender 단독 실행

`python tools\mock_sender.py` — 6 rounds × 5 people = **30 detections** 전부 성공.

```
Round 1/6  ts≈01:15:57  → 모두 matched=False (신규 person 생성: gid 2~6)
Round 2/6  ts≈01:35:57  → 모두 matched=True
Round 3/6  ts≈01:55:57  → 모두 matched=True
Round 4/6  ts≈02:15:57  → 모두 matched=True
Round 5/6  ts≈02:35:57  → 모두 matched=True   ← regular 승격 발생
Round 6/6  ts≈02:55:57  → 모두 matched=True
```

### 3.3 결과 요약 (mock_sender 자체 호출)

- `GET /api/v1/retail/vips` → 200, `[]` (VIP 수동 지정 전이라 정상)
- `GET /api/v1/retail/persons?limit=20` → 200
  - gid 2~6: `tier=regular`, `is_vip=False`, `visit_count=6`, `last_visit_at=2026-05-20T02:55:57Z`
  - gid 1: `tier=new`, `visit_count=0` ← 사전 잔존(아래 § 5 참조)
- `GET /api/v1/retail/stats/hourly?days=7` → 200
  - hour 1: visits=15, unique_visitors=5
  - hour 2: visits=15, unique_visitors=5

### 3.4 DB 직접 확인

`person_visits` 테이블 최근 10 행:

| visit_id | global_id | started_at | ended_at | detection_count |
|---:|---:|---|---|---:|
| 30 | 6 | 02:55:57 | 02:55:57 | 1 |
| 29 | 5 | 02:55:57 | 02:55:57 | 1 |
| 28 | 4 | 02:55:57 | 02:55:57 | 1 |
| 27 | 3 | 02:55:57 | 02:55:57 | 1 |
| 26 | 2 | 02:55:57 | 02:55:57 | 1 |
| 25 | 6 | 02:35:57 | 02:35:57 | 1 |
| ... | | | | |
| 21 | 2 | 02:35:57 | 02:35:57 | 1 |

→ 라운드별 visit 가 사람별 분리되어 정상 적재됨.

---

## 4. 관찰 — 시스템 문제 아님

- **`avg_duration_sec = 0`**: mock_sender 가 라운드당 사람별 1 detection 만 보내므로 visit 의 `started_at == ended_at`. 실제 엣지에서 연속 frame 이 흐르면 자연히 누적되는 값. mock 데이터의 한계일 뿐 분석 로직은 문제 없음.

- **임계값 `0.85` 와 매칭 안정성**: 같은 seed 의 embedding 은 동일 벡터를 만들어 Round 2 부터는 모두 매칭. 실제 OSNet embedding 의 분산이 커지면 임계값 재조정이 필요할 수 있음 (팀장님 OSNet 연동 후 별도 튜닝 항목).

---

## 5. 다음 작업 후보

1. **시연 전 DB cleanup**: `gid=1, tier=new` 잔존(마이그레이션 적용 전 dry-run 흔적) 제거. 한 줄 쿼리로 가능.
2. **WebSocket 알림 검증**: `/api/v1/security/ws/alerts` 에 클라이언트 붙여 `regular_visit` 알림 수신 확인.
3. **VIP 운영 흐름 검증**: `POST /api/v1/retail/persons/{gid}/vip` → `GET /vips` 응답 확인.
4. **matcher.py 별도 커밋**: `find_or_create_global_id` 의 None 가드 + 타입 정리 (DB fix 와 무관해 별도 커밋 예정).
5. **임계값/dwell threshold 튜닝**: 팀장님 OSNet 연동 후 실측 embedding 분포 기반으로 조정.

---

## 6. 참고

- 푸시: `https://github.com/artport-max/EYE-D` 의 `feature/eyed-retail-vip-dwell`
- 이번 커밋: `1be4618..f672f03`
- 변경 4 files, +8 / -5
