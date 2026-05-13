"""
test_pipeline_runner.py
-----------------------
PipelineRunner의 오케스트레이션 로직 단위 테스트.

실제 모델(YOLO, BoxMOT, OSNet, Qdrant) 없이 Mock을 주입하여
PipelineRunner의 "조립 로직"과 "흐름 제어"만 격리 검증합니다.

테스트 범위:
  [초기화] 컴포넌트 주입 및 상태 확인
  [정상 흐름] process_frame() 결과 구조 검증
  [DB 연동] Mock DB에 벡터가 저장되는지 확인
  [에러 격리] DB 없을 때 파이프라인이 계속 동작하는지 확인
  [배치] process_batch() 다중 카메라 처리
"""

import pytest
from unittest.mock import MagicMock, patch

from src.core.pipeline_runner import PipelineRunner
from tests.harness.mocks import (
    MockVectorDBClient,
    MockDetector,
    MockTracker,
    MockReIDExtractor,
)
from tests.harness.fixtures import dummy_bgr_frame


# ==========================================================================
# 헬퍼: 실제 모델 초기화 없이 PipelineRunner를 구성하는 팩토리
# ==========================================================================

def make_pipeline(db_client=None):
    """
    _initialize_models()를 Mock으로 우회하여
    무거운 모델 로딩 없이 PipelineRunner를 생성합니다.
    """
    runner = PipelineRunner(config={}, db_client=db_client)
    runner._detector = MockDetector(num_detections=2)
    runner._tracker = MockTracker(track_ids=[1, 2])
    runner._reid = MockReIDExtractor(vector_dim=512)
    runner.running = True
    return runner


# ==========================================================================
# [초기화 테스트]
# ==========================================================================

class TestPipelineRunnerInit:
    """PipelineRunner 초기화 관련 테스트."""

    def test_default_config_applied(self):
        """config 없이 생성 시 기본값이 적용되어야 한다."""
        runner = PipelineRunner()
        assert runner.config == {}
        assert runner.collection_name == 'reid_collection'
        assert runner.running is False
        assert runner.frames_processed == 0

    def test_custom_collection_name(self):
        """config에 collection_name 지정 시 반영되어야 한다."""
        runner = PipelineRunner(config={'collection_name': 'custom_col'})
        assert runner.collection_name == 'custom_col'

    def test_db_client_injection(self):
        """db_client를 주입하면 내부에 저장되어야 한다."""
        mock_db = MockVectorDBClient()
        runner = PipelineRunner(db_client=mock_db)
        assert runner.db_client is mock_db

    def test_no_db_client_is_valid(self):
        """db_client 없이도 인스턴스 생성에 성공해야 한다."""
        runner = PipelineRunner()
        assert runner.db_client is None

    def test_initial_state_not_running(self):
        """생성 직후 running은 False여야 한다."""
        runner = PipelineRunner()
        assert runner.running is False


# ==========================================================================
# [process_frame 정상 흐름 테스트]
# ==========================================================================

class TestProcessFrame:
    """process_frame() 정상 흐름 테스트."""

    def test_returns_dict_with_required_keys(self, frame):
        """process_frame() 결과에 필수 키가 모두 존재해야 한다."""
        runner = make_pipeline()
        result = runner.process_frame(frame, camera_id='cam_01')

        assert result is not None
        assert 'frame_index' in result
        assert 'camera_id' in result
        assert 'detections' in result
        assert 'tracks' in result
        assert 'reid_vectors' in result
        assert 'processing_time_ms' in result

    def test_camera_id_propagated_to_result(self, frame):
        """입력한 camera_id가 결과에 정확히 반영되어야 한다."""
        runner = make_pipeline()
        result = runner.process_frame(frame, camera_id='cam_99')
        assert result['camera_id'] == 'cam_99'

    def test_frame_index_increments(self, frame):
        """호출할 때마다 frame_index가 1씩 증가해야 한다."""
        runner = make_pipeline()
        r1 = runner.process_frame(frame)
        r2 = runner.process_frame(frame)
        r3 = runner.process_frame(frame)
        assert r1['frame_index'] == 1
        assert r2['frame_index'] == 2
        assert r3['frame_index'] == 3

    def test_returns_none_when_not_running(self, frame):
        """running=False 상태에서 process_frame()은 None을 반환해야 한다."""
        runner = make_pipeline()
        runner.running = False
        result = runner.process_frame(frame)
        assert result is None

    def test_returns_none_for_none_frame(self):
        """frame이 None이면 None을 반환해야 한다."""
        runner = make_pipeline()
        result = runner.process_frame(None)
        assert result is None

    def test_reid_vectors_have_correct_structure(self, frame):
        """reid_vectors의 각 요소는 track_id와 vector를 가져야 한다."""
        runner = make_pipeline()
        result = runner.process_frame(frame)

        assert len(result['reid_vectors']) > 0
        for rv in result['reid_vectors']:
            assert 'track_id' in rv
            assert 'vector' in rv
            assert isinstance(rv['vector'], list)
            assert len(rv['vector']) == 512

    def test_processing_time_is_positive(self, frame):
        """처리 시간은 0보다 커야 한다."""
        runner = make_pipeline()
        result = runner.process_frame(frame)
        assert result['processing_time_ms'] >= 0


# ==========================================================================
# [DB 연동 테스트]
# ==========================================================================

class TestPipelineRunnerWithDB:
    """DB 주입 시 저장 동작 테스트."""

    def test_vectors_saved_to_db_after_process(self, frame):
        """process_frame() 후 Mock DB에 벡터가 저장되어야 한다."""
        mock_db = MockVectorDBClient()
        runner = make_pipeline(db_client=mock_db)

        runner.process_frame(frame, camera_id='cam_01')

        assert mock_db.upsert_call_count == 1
        assert mock_db.total_record_count('reid_collection') == 2  # track_id 1, 2

    def test_db_records_contain_camera_id_in_payload(self, frame):
        """DB에 저장된 레코드의 payload에 camera_id가 있어야 한다."""
        mock_db = MockVectorDBClient()
        runner = make_pipeline(db_client=mock_db)

        runner.process_frame(frame, camera_id='cam_42')

        records = mock_db.get_records('reid_collection')
        assert all(r['payload']['camera_id'] == 'cam_42' for r in records)

    def test_no_db_upsert_when_no_db_client(self, frame):
        """db_client가 None이면 DB 저장을 시도하지 않아도 파이프라인은 성공해야 한다."""
        runner = make_pipeline(db_client=None)
        result = runner.process_frame(frame)
        # 예외 없이 정상 결과 반환
        assert result is not None

    def test_db_upsert_failure_does_not_crash_pipeline(self, frame):
        """DB 저장 실패 시 예외가 파이프라인 밖으로 전파되지 않아야 한다."""
        mock_db = MockVectorDBClient()
        # upsert에서 예외 발생하도록 강제 재정의
        mock_db.upsert = MagicMock(side_effect=RuntimeError("Qdrant 연결 끊김"))

        runner = make_pipeline(db_client=mock_db)
        # 예외가 발생해도 결과를 반환해야 함 (Null-safe 정책)
        result = runner.process_frame(frame)
        assert result is not None


# ==========================================================================
# [배치 처리 테스트]
# ==========================================================================

class TestProcessBatch:
    """process_batch() 다중 카메라 처리 테스트."""

    def test_batch_returns_result_for_each_camera(self, frame):
        """frames_dict의 각 카메라 키에 대한 결과가 반환되어야 한다."""
        runner = make_pipeline()
        frames = {'cam_01': frame, 'cam_02': frame}
        results = runner.process_batch(frames)

        assert 'cam_01' in results
        assert 'cam_02' in results

    def test_batch_none_frame_returns_none(self, frame):
        """frames_dict에서 None 프레임은 None 결과를 반환해야 한다."""
        runner = make_pipeline()
        frames = {'cam_01': frame, 'cam_02': None}
        results = runner.process_batch(frames)

        assert results['cam_01'] is not None
        assert results['cam_02'] is None

    def test_batch_camera_ids_propagated(self, frame):
        """배치 처리 결과의 camera_id가 키와 일치해야 한다."""
        runner = make_pipeline()
        frames = {'cam_A': frame, 'cam_B': frame}
        results = runner.process_batch(frames)

        assert results['cam_A']['camera_id'] == 'cam_A'
        assert results['cam_B']['camera_id'] == 'cam_B'


# ==========================================================================
# [생명주기 테스트]
# ==========================================================================

class TestPipelineLifecycle:
    """start() / stop() 생명주기 테스트."""

    def test_stop_sets_running_false(self):
        """stop() 호출 후 running이 False여야 한다."""
        runner = make_pipeline()
        runner.stop()
        assert runner.running is False

    def test_get_intermediate_results_structure(self):
        """get_intermediate_results()가 올바른 키를 반환해야 한다."""
        runner = make_pipeline()
        status = runner.get_intermediate_results()

        assert 'frames_processed' in status
        assert 'detector_loaded' in status
        assert 'tracker_loaded' in status
        assert 'reid_loaded' in status
        assert status['detector_loaded'] is True
        assert status['tracker_loaded'] is True
        assert status['reid_loaded'] is True
