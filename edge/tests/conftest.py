import pytest
import numpy as np
from tests.harness.fixtures import dummy_bgr_frame, dummy_track_results, dummy_reid_vector
from tests.harness.mocks import (
    MockVectorDBClient,
    MockHTTPSender,
    MockDetector,
    MockTracker,
    MockReIDExtractor,
)


# ──────────────────────────── 기본 데이터 피스처 ────────────────────────────

@pytest.fixture
def frame():
    """640x480 크기의 더미 BGR 프레임 피스처."""
    return dummy_bgr_frame()


@pytest.fixture
def tracks():
    """2개의 TrackResult를 포함하는 더미 리스트 피스처."""
    return dummy_track_results()


@pytest.fixture
def reid_vector():
    """512차원 더미 Re-ID 벡터 피스처."""
    return dummy_reid_vector()


@pytest.fixture
def mock_config():
    """테스트용 기본 설정 딕셔너리."""
    return {
        "device_id": "test_edge_01",
        "camera_id": "test_cam_01",
        "server_url": "http://localhost:8000/api/v1",
        "send_every_n_frames": 5,
    }


# ──────────────────────────── Mock 인프라 피스처 ─────────────────────────────

@pytest.fixture
def mock_db():
    """격리된 in-memory VectorDBClient Mock."""
    return MockVectorDBClient()


@pytest.fixture
def mock_db_failing():
    """항상 연결 실패하는 VectorDBClient Mock."""
    return MockVectorDBClient(connect_should_fail=True)


@pytest.fixture
def mock_sender():
    """HTTP POST 전송 Mock (항상 성공)."""
    return MockHTTPSender()


@pytest.fixture
def mock_sender_failing():
    """HTTP POST 전송 Mock (항상 실패 — 서버 다운 시뮬레이션)."""
    return MockHTTPSender(should_fail=True)


@pytest.fixture
def mock_sender_flaky():
    """처음 2번만 성공하고 이후 실패하는 Mock (불안정 네트워크 시뮬레이션)."""
    return MockHTTPSender(fail_after_n=2)


# ──────────────────────────── Mock 코어 컴포넌트 피스처 ──────────────────────

@pytest.fixture
def mock_detector():
    """탐지 결과 2개를 반환하는 PersonDetector Mock."""
    return MockDetector(num_detections=2)


@pytest.fixture
def mock_tracker():
    """track_id [1, 2] 를 반환하는 PersonTracker Mock."""
    return MockTracker(track_ids=[1, 2])


@pytest.fixture
def mock_reid():
    """512차원 랜덤 벡터를 반환하는 ReIDExtractor Mock."""
    return MockReIDExtractor(vector_dim=512)
