-- ============================================================
-- 실제 영상 테스트 전 DB 초기화
-- ------------------------------------------------------------
-- 비우는 것 : detections, persons, person_visits, zone_visits
-- 유지하는 것: cameras (사전 등록 카메라), zones (사전 등록 구역)
--
-- 적용 방법 (Windows PowerShell, EYE-D/server 위치):
--   Get-Content .\app\db\maintenance\reset_for_test.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
--
-- 적용 방법 (Linux/macOS, EYE-D/server 위치):
--   cat app/db/maintenance/reset_for_test.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
--
-- 주의: 이 스크립트는 데이터를 영구 삭제합니다. 실제 데이터가 있는 환경에서 실행 금지.
-- ============================================================

BEGIN;

-- CASCADE 로 detections / person_visits / zone_visits 까지 함께 정리
TRUNCATE TABLE
    zone_visits,
    person_visits,
    detections,
    persons
RESTART IDENTITY CASCADE;

-- 정리 결과 확인 (모두 0 이어야 함)
SELECT 'persons'        AS table_name, COUNT(*) AS row_count FROM persons
UNION ALL
SELECT 'detections',      COUNT(*) FROM detections
UNION ALL
SELECT 'person_visits',   COUNT(*) FROM person_visits
UNION ALL
SELECT 'zone_visits',     COUNT(*) FROM zone_visits
UNION ALL
SELECT 'cameras (유지)',  COUNT(*) FROM cameras
UNION ALL
SELECT 'zones (유지)',    COUNT(*) FROM zones;

COMMIT;
