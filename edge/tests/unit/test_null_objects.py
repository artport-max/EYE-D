"""
test_null_objects.py
--------------------
Phase 2: NullDBClient, NullSender의 동작 단위 테스트.

Null Object들이 올바르게 인터페이스를 준수하면서
예외 없이 "아무것도 안 함"을 보장하는지 검증합니다.
"""

import pytest
from src.infrastructure.null_objects import NullDBClient, NullSender
from src.core.pipeline_runner import PipelineRunner
from tests.harness.mocks import MockVectorDBClient, MockHTTPSender
from tests.harness.fixtures import dummy_bgr_frame
from tests.harness.mocks import MockDetector, MockTracker, MockReIDExtractor


# ==========================================================================
# NullDBClient 테스트
# ==========================================================================

class TestNullDBClient:
    """NullDBClient가 인터페이스를 준수하면서 예외 없이 동작하는지 검증."""

    def setup_method(self):
        self.null_db = NullDBClient()

    def test_connect_returns_false(self):
        """NullDBClient.connect()는 False를 반환해야 한다."""
        result = self.null_db.connect()
        assert result is False

    def test_collection_exists_always_false(self):
        """NullDBClient.collection_exists()는 항상 False를 반환해야 한다."""
        assert self.null_db.collection_exists('any_collection') is False

    def test_upsert_returns_false_without_exception(self):
        """NullDBClient.upsert()는 예외 없이 False를 반환해야 한다."""
        result = self.null_db.upsert('col', [{'id': 1, 'vector': [0.1] * 512}])
        assert result is False

    def test_search_returns_empty_result(self):
        """NullDBClient.search()는 빈 hits 구조를 반환해야 한다."""
        result = self.null_db.search('col', [0.0] * 512)
        assert result['hits'] == []
        assert result['hit_count'] == 0

    def test_index_exists_always_false(self):
        """NullDBClient.index_exists()는 항상 False를 반환해야 한다."""
        assert self.null_db.index_exists('any_collection') is False

    def test_ensure_collection_no_exception(self):
        """NullDBClient.ensure_collection()은 예외 없이 완료되어야 한다."""
        self.null_db.ensure_collection('test_col', vector_size=512)  # 예외 없음


# ==========================================================================
# NullSender 테스트
# ==========================================================================

class TestNullSender:
    """NullSender가 인터페이스를 준수하면서 예외 없이 동작하는지 검증."""

    def setup_method(self):
        self.null_sender = NullSender()

    def test_post_returns_zero_status_code(self):
        """NullSender.post()는 (0, {})를 반환해야 한다 (전송 안 됨 표시)."""
        status, body = self.null_sender.post('/api/v1/vectors', {'tracks': []})
        assert status == 0
        assert body == {}

    def test_post_does_not_raise_on_any_payload(self):
        """NullSender.post()는 어떤 페이로드에도 예외를 발생시키지 않아야 한다."""
        self.null_sender.post('/api/v1/vectors', {})
        self.null_sender.post('/api/v1/events', {'event_type': 'zone_entry'})
        self.null_sender.post('/api/v1/heartbeat', {'device_id': 'edge_01'})

    def test_send_vectors_returns_false(self):
        """NullSender.send_vectors()는 False를 반환해야 한다."""
        assert self.null_sender.send_vectors() is False

    def test_send_event_returns_false(self):
        """NullSender.send_event()는 False를 반환해야 한다."""
        assert self.null_sender.send_event() is False

    def test_send_heartbeat_returns_false(self):
        """NullSender.send_heartbeat()는 False를 반환해야 한다."""
        assert self.null_sender.send_heartbeat() is False


# ==========================================================================
# PipelineRunner + Null Object 통합 테스트
# ==========================================================================

def make_pipeline_with_mocks(db_client=None, http_sender=None):
    """DI로 Mock 또는 Null을 주입하는 파이프라인 팩토리."""
    runner = PipelineRunner(config={}, db_client=db_client, http_sender=http_sender)
    runner._detector = MockDetector(num_detections=2)
    runner._tracker = MockTracker(track_ids=[1, 2])
    runner._reid = MockReIDExtractor(vector_dim=512)
    runner.running = True
    return runner


class TestPipelineWithNullObjects:
    """Null Object가 주입됐을 때 파이프라인 동작 검증."""

    def test_no_args_uses_null_objects_automatically(self):
        """db_client, http_sender 미주입 시 Null Object가 자동으로 설정되어야 한다."""
        runner = PipelineRunner()
        assert type(runner.db_client).__name__ == 'NullDBClient'
        assert type(runner.http_sender).__name__ == 'NullSender'

    def test_real_db_injection_replaces_null(self):
        """실제 MockDB를 주입하면 NullDBClient가 아니어야 한다."""
        mock_db = MockVectorDBClient()
        runner = PipelineRunner(db_client=mock_db)
        assert type(runner.db_client).__name__ != 'NullDBClient'
        assert runner.db_client is mock_db

    def test_real_sender_injection_replaces_null(self):
        """실제 MockSender를 주입하면 NullSender가 아니어야 한다."""
        mock_sender = MockHTTPSender()
        runner = PipelineRunner(http_sender=mock_sender)
        assert type(runner.http_sender).__name__ != 'NullSender'
        assert runner.http_sender is mock_sender

    def test_pipeline_runs_with_all_null_objects(self):
        """DB/서버 모두 없어도 파이프라인이 예외 없이 실행되어야 한다."""
        runner = make_pipeline_with_mocks(db_client=None, http_sender=None)
        frame = dummy_bgr_frame()
        result = runner.process_frame(frame, camera_id='cam_01')
        assert result is not None
        assert result['frame_index'] == 1

    def test_server_sender_called_when_injected(self):
        """MockHTTPSender 주입 시 process_frame() 후 POST가 1회 호출되어야 한다."""
        mock_sender = MockHTTPSender()
        runner = make_pipeline_with_mocks(http_sender=mock_sender)
        frame = dummy_bgr_frame()

        runner.process_frame(frame, camera_id='cam_01')

        assert mock_sender.call_count == 1
        assert mock_sender.last_endpoint == '/api/v1/vectors'

    def test_server_payload_contains_camera_id(self):
        """서버 전송 페이로드에 camera_id가 포함되어야 한다."""
        mock_sender = MockHTTPSender()
        runner = make_pipeline_with_mocks(http_sender=mock_sender)
        frame = dummy_bgr_frame()

        runner.process_frame(frame, camera_id='cam_42')

        payload = mock_sender.last_payload
        assert payload['camera_id'] == 'cam_42'

    def test_server_payload_tracks_have_vector(self):
        """서버 전송 페이로드의 각 track에 512차원 vector가 있어야 한다."""
        mock_sender = MockHTTPSender()
        runner = make_pipeline_with_mocks(http_sender=mock_sender)
        frame = dummy_bgr_frame()

        runner.process_frame(frame)

        tracks = mock_sender.last_payload['tracks']
        assert len(tracks) > 0
        for track in tracks:
            assert 'track_id' in track
            assert 'vector' in track
            assert len(track['vector']) == 512

    def test_get_intermediate_results_shows_configured_state(self):
        """실제 DB/Sender 주입 시 get_intermediate_results에서 configured=True여야 한다."""
        runner = make_pipeline_with_mocks(
            db_client=MockVectorDBClient(),
            http_sender=MockHTTPSender(),
        )
        status = runner.get_intermediate_results()
        assert status['db_configured'] is True
        assert status['sender_configured'] is True

    def test_get_intermediate_results_shows_null_state(self):
        """Null Object 사용 시 get_intermediate_results에서 configured=False여야 한다."""
        runner = make_pipeline_with_mocks(db_client=None, http_sender=None)
        status = runner.get_intermediate_results()
        assert status['db_configured'] is False
        assert status['sender_configured'] is False
