-- ============================================================
-- 2026-05-19 Smart Retail Phase A + 체류·동선 특징 분석
-- ------------------------------------------------------------
-- 적용 대상: schema.sql 로 초기화된 EYE-D DB
-- 안전성  : 기존 컬럼/테이블을 깨지 않음 (모두 IF NOT EXISTS / ADD COLUMN)
-- 적용 방법 (Windows PowerShell, 호스트에 psql 없어도 동작):
--   Get-Content .\app\db\migrations\2026-05-19_retail.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
-- 호스트에 psql 이 있고 직접 붙고 싶다면 (포트 5433 주의):
--   psql -h localhost -p 5433 -U eyed -d eyed -f app/db/migrations/2026-05-19_retail.sql
-- ============================================================

-- 1) persons 테이블에 고객 분류 컬럼 추가
ALTER TABLE persons
    ADD COLUMN IF NOT EXISTS is_vip         BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS customer_tier  TEXT        NOT NULL DEFAULT 'new',
    ADD COLUMN IF NOT EXISTS visit_count    INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_visit_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS display_name   TEXT,           -- VIP 라벨용 표시명 (옵션)
    ADD COLUMN IF NOT EXISTS notes          TEXT;           -- 운영자 메모

-- customer_tier 허용 값 체크 제약
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'persons_customer_tier_chk'
    ) THEN
        ALTER TABLE persons
            ADD CONSTRAINT persons_customer_tier_chk
            CHECK (customer_tier IN ('new', 'returning', 'regular', 'vip'));
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_persons_is_vip ON persons (is_vip);
CREATE INDEX IF NOT EXISTS idx_persons_tier   ON persons (customer_tier);


-- 2) person_visits — 한 번의 방문(=재방문 묶음). 체류 분석 기본 단위
CREATE TABLE IF NOT EXISTS person_visits (
    visit_id        BIGSERIAL PRIMARY KEY,
    global_id       INTEGER     NOT NULL REFERENCES persons(global_id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ NOT NULL,
    duration_sec    REAL GENERATED ALWAYS AS (
                        EXTRACT(EPOCH FROM (ended_at - started_at))
                    ) STORED,
    detection_count INTEGER     NOT NULL DEFAULT 0,
    primary_camera  TEXT,                         -- 가장 오래 머문 카메라
    is_intrusion    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_person_visits_gid_time
    ON person_visits (global_id, started_at DESC);


-- 3) zones — 운영자가 정의하는 공간 구역 (입구/계산대/매장A 등)
CREATE TABLE IF NOT EXISTS zones (
    zone_id    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    camera_id  TEXT REFERENCES cameras(camera_id),
    polygon    JSONB,                              -- 카메라 좌표계 다각형 (옵션)
    purpose    TEXT,                               -- 'entrance' | 'checkout' | 'display' | ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 4) zone_visits — 한 사람이 한 zone 에 머문 한 구간
CREATE TABLE IF NOT EXISTS zone_visits (
    zone_visit_id   BIGSERIAL PRIMARY KEY,
    visit_id        BIGINT      REFERENCES person_visits(visit_id) ON DELETE CASCADE,
    global_id       INTEGER     NOT NULL REFERENCES persons(global_id),
    zone_id         TEXT        NOT NULL REFERENCES zones(zone_id),
    entered_at      TIMESTAMPTZ NOT NULL,
    exited_at       TIMESTAMPTZ NOT NULL,
    dwell_sec       REAL GENERATED ALWAYS AS (
                        EXTRACT(EPOCH FROM (exited_at - entered_at))
                    ) STORED,
    detection_count INTEGER     NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_zone_visits_gid_time
    ON zone_visits (global_id, entered_at DESC);
CREATE INDEX IF NOT EXISTS idx_zone_visits_zone_time
    ON zone_visits (zone_id, entered_at DESC);


-- 5) 시연용 zone 1개 미리 등록 (CAM_01 매장 전체 가정)
INSERT INTO zones (zone_id, name, camera_id, purpose)
VALUES ('Z_MAIN', 'PS Center main hall', 'CAM_01', 'entrance')
ON CONFLICT (zone_id) DO NOTHING;
