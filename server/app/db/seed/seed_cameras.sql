-- ============================================================
-- PS Center 3대 카메라 사전 등록 (실제 테스트 준비)
-- ------------------------------------------------------------
-- 카메라 ID 는 엣지에서 detection 보낼 때 그대로 사용하는 키.
-- rtsp_url 은 다음 중 하나:
--   - 실시간 RTSP 스트림 URL  (운영 환경)
--   - 변환된 MP4 파일의 절대경로 (오프라인 테스트 — file:// 또는 그대로)
--   - 비어두기 (엣지에서 직접 source 지정 시)
--
-- 적용 방법 (Windows PowerShell, EYE-D/server 위치):
--   Get-Content .\app\db\seed\seed_cameras.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
--
-- 적용 방법 (Linux/macOS, EYE-D/server 위치):
--   cat app/db/seed/seed_cameras.sql | docker exec -i eyed-postgres psql -U eyed -d eyed
--
-- ON CONFLICT 으로 멱등성 보장 — 여러 번 실행해도 안전.
-- ============================================================

INSERT INTO cameras (camera_id, location, rtsp_url) VALUES
    ('CAM_01', 'PS Center main hall',  'C:/Users/murim/OneDrive/문서/Claude/Projects/엣지 게이트웨이 기반 지능형 침입 탐지 및 인물 재식별(Re-ID) 시스템/EYE-D/data/converted/16300000.avi'),
    ('CAM_02', 'PS Center side entry', ''),  -- TODO: SSF 변환 완료 후 실제 경로로 갱신
    ('CAM_03', 'PS Center back room',  '')   -- TODO: SSF 변환 완료 후 실제 경로로 갱신
ON CONFLICT (camera_id) DO UPDATE
    SET location = EXCLUDED.location,
        rtsp_url = EXCLUDED.rtsp_url;

-- 등록 결과 확인
SELECT camera_id, location, rtsp_url, created_at FROM cameras ORDER BY camera_id;
