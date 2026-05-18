-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 카메라 메타
CREATE TABLE IF NOT EXISTS cameras (
    camera_id   TEXT PRIMARY KEY,
    location    TEXT,
    rtsp_url    TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 사람 (글로벌 ID)
CREATE TABLE IF NOT EXISTS persons (
    global_id     SERIAL PRIMARY KEY,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 탐지 이벤트
CREATE TABLE IF NOT EXISTS detections (
    detection_id        BIGSERIAL PRIMARY KEY,
    camera_id           TEXT REFERENCES cameras(camera_id),
    global_id           INTEGER REFERENCES persons(global_id),
    tracklet_id         TEXT NOT NULL,
    embedding_identity  vector(512) NOT NULL,
    bbox                JSONB,
    detected_at         TIMESTAMPTZ NOT NULL,
    is_intrusion        BOOLEAN DEFAULT FALSE,

    -- arttrace 확장 슬롯 (NULL 허용)
    pose_keypoints   JSONB,
    action_label     TEXT,
    dwell_seconds    REAL,
    appearance_attrs JSONB,
    scene_context    JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 임베딩 유사도 검색 인덱스
CREATE INDEX IF NOT EXISTS idx_detections_embedding
    ON detections USING ivfflat (embedding_identity vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_detections_global_id_time
    ON detections (global_id, detected_at);

-- arttrace 진입 시 채워질 테이블 (지금은 자리만)
CREATE TABLE IF NOT EXISTS art_events (
    event_id            BIGSERIAL PRIMARY KEY,
    detection_id        BIGINT REFERENCES detections(detection_id),
    mood_vector         vector(64),
    generated_text      TEXT,
    generated_audio_path TEXT,
    agent_trace         JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 시연용 카메라 1개 미리 등록
INSERT INTO cameras (camera_id, location)
VALUES ('CAM_01', 'PS Center main hall')
ON CONFLICT (camera_id) DO NOTHING;