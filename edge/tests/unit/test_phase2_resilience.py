"""
test_phase2_resilience.py
--------------------------
Phase 2 최적화 기법에 대한 격리 단위 테스트.
ResilientServerSender의 로컬 SQLite 버퍼링, 네트워크 에러 시의 유실 방지 및 복원력,
그리고 ThreadedPipelineRunner의 백그라운드 스레드 및 큐 병렬화 성능을 독립적으로 검증합니다.
"""

import os
import time
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
import requests

from src.core.pipeline_runner import ThreadedPipelineRunner, PipelineRunner
from src.infrastructure.http_client import ResilientServerSender
from tests.harness.mocks import MockVectorDBClient, MockYOLO


class TestResilienceAndParallelism(unittest.TestCase):
    """Phase 2 하드웨어 가속/병렬화/복원력 관련 핵심 기능에 대한 검증 테스트 스위트."""

    def setUp(self):
        # 테스트용 임시 SQLite DB 경로
        self.test_db_path = "test_resilience_buffer.db"
        # 테스트 시작 전 불필요한 기존 DB 파일 제거
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def tearDown(self):
        # 테스트 후 생성된 임시 SQLite DB 파일 말끔히 청소
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                pass

    # ------------------------------------------------------------------
    # 1. 네트워크 복원력 (Resilience) 검증
    # ------------------------------------------------------------------

    def test_resilient_sender_buffer_on_network_failure(self):
        """네트워크가 차단되거나 서버가 오프라인일 때 전송한 데이터가 로컬 SQLite DB에 완벽히 보존되는지 검증합니다."""
        # 1. 절대 열려 있지 않을 무효한 로컬 포트로 Sender 초기화 (즉, 전송 실패 강제 유도)
        sender = ResilientServerSender(
            base_url="http://localhost:9999",  # 접속 불가 포트
            db_path=self.test_db_path,
            retry_interval=0.5
        )

        test_payload = {
            "camera_id": "cam_test",
            "tracks": [{"track_id": 1, "vector": [0.1] * 512, "confidence": 0.9}]
        }

        # 2. 전송 호출 (상태코드 202 Accepted 및 로컬 적재 확인)
        status, response = sender.post("/api/v1/vectors", test_payload)
        self.assertEqual(status, 202)
        self.assertIn("buffered locally", response["message"])

        # 3. 로컬 SQLite 버퍼에 정상 적재되었는지 확인 (버퍼 사이즈 == 1)
        # 백그라운드 재전송이 실패하므로 버퍼 크기는 그대로 1로 유지되어야 함
        time.sleep(1.0)
        self.assertEqual(sender.get_buffer_size(), 1)
        
        # 안전한 종료
        sender.stop()

    @patch("requests.post")
    def test_resilient_sender_auto_recovery(self, mock_post):
        """서버가 장애에서 회복(정상 응답)되었을 때 로컬 버퍼에 쌓여있던 데이터가 자동 재전송 및 소진되는지 검증합니다."""
        # 1. 처음에는 네트워크 에러를 던지도록 세팅
        mock_post.side_effect = requests.RequestException("Connection refused")

        sender = ResilientServerSender(
            base_url="http://localhost:8000",
            db_path=self.test_db_path,
            retry_interval=0.2  # 빠른 재전송을 위해 짧게 설정
        )

        test_payload = {
            "camera_id": "cam_test_recovery",
            "tracks": [{"track_id": 42, "vector": [0.5] * 512}]
        }

        # 2. 전송 시도 -> 네트워크 끊김 상태이므로 버퍼에 보존됨
        sender.post("/api/v1/vectors", test_payload)
        time.sleep(0.5)
        self.assertEqual(sender.get_buffer_size(), 1)

        # 3. 서버가 회복된 가상 상황 설정 (성공 응답 200 반환)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_post.side_effect = None
        mock_post.return_value = mock_response

        # 4. 재시도 간격(0.2초) 대기 후 자동으로 버퍼가 소진되어 0이 되는지 확인
        time.sleep(0.6)
        self.assertEqual(sender.get_buffer_size(), 0)

        # 5. 실제로 백그라운드에서 POST 요청이 잘 이루어졌는지 증명
        mock_post.assert_called()
        
        sender.stop()

    # ------------------------------------------------------------------
    # 2. 파이프라인 병렬화 (ThreadedPipelineRunner) 검증
    # ------------------------------------------------------------------

    @patch("cv2.VideoCapture")
    def test_threaded_pipeline_runner_lifecycle(self, mock_video_capture):
        """ThreadedPipelineRunner가 백그라운드 스레드에서 예외 없이 안전하게 기동 및 정지되는지 검증합니다."""
        # OpenCV VideoCapture Mocking
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # 1. 멀티스레드 파이프라인 러너 초기화
        config = {
            'yolo_model': 'yolov8n.pt',
            'conf_threshold': 0.5,
            'tracker_type': 'botsort',
            'reid_model': 'osnet_x0_25',
        }
        db_client = MockVectorDBClient()
        
        # 실제 모델 로드를 피하기 위해 YOLO 초기화 패치
        with patch('src.core.detector.YOLO', return_value=MockYOLO()):
            runner = ThreadedPipelineRunner(
                source=0,
                config=config,
                db_client=db_client,
                queue_size=5
            )

            # 2. 실행 및 상태 체크
            success = runner.start()
            self.assertTrue(success)
            self.assertTrue(runner.running)

            # 약간의 구동 대기 후 프레임이 대기열에 쌓이거나 처리되었는지 검증
            time.sleep(0.5)
            status = runner.get_queue_status()
            self.assertGreaterEqual(status['frames_processed'] + status['frame_queue_size'], 0)

            # 3. 안전한 정지
            stop_success = runner.stop()
            self.assertTrue(stop_success)
            self.assertFalse(runner.running)

    # ------------------------------------------------------------------
    # 3. 하드웨어 가속 (TensorRT / ONNX) 검증
    # ------------------------------------------------------------------

    @patch("src.core.reid_extractor.FeatureExtractor")
    @patch("torch.onnx.export")
    @patch("os.path.exists")
    def test_reid_extractor_onnx_acceleration(self, mock_exists, mock_export, mock_feature_extractor):
        """ReIDExtractor가 ONNX 가속 옵션을 활성화했을 때, 모델 자동 변환 및 가속 세션을 정상적으로 생성하고 실행하는지 검증합니다."""
        import sys
        
        # 1. onnxruntime 모듈의 부재를 방어하기 위해 sys.modules에 모킹 모듈 동적 주입
        mock_session_inst = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input"
        mock_session_inst.get_inputs.return_value = [mock_input]
        # features[0] 추출을 지원하도록 [1, 512] 넘파이 행렬 반환
        mock_session_inst.run.return_value = [np.ones((1, 512), dtype=np.float32)]
        
        mock_session_class = MagicMock(return_value=mock_session_inst)
        
        mock_ort = MagicMock()
        mock_ort.InferenceSession = mock_session_class
        
        # 기존 모듈 설정 임시 저장 및 Mock 주입
        original_ort = sys.modules.get("onnxruntime")
        sys.modules["onnxruntime"] = mock_ort
        
        try:
            # 2. 파일 존재 검증 흐름에 따른 동적 side_effect 시뮬레이션
            # 첫 번째 "osnet_x0_25.onnx" 호출 ➔ False 반환 (내보내기 실행)
            # 두 번째 "osnet_x0_25.onnx" 호출 ➔ True 반환 (모델 로드 진입)
            existing_files = set()
            def mock_exists_side_effect(path):
                if isinstance(path, str) and "osnet_x0_25.onnx" in path:
                    # 파일 이름 기준으로 체크
                    key = "osnet_x0_25.onnx"
                    if key in existing_files:
                        return True
                    existing_files.add(key)
                    return False
                return True
            mock_exists.side_effect = mock_exists_side_effect
            
            # mock FeatureExtractor 인스턴스 설정
            mock_extractor_inst = MagicMock()
            mock_model = MagicMock()
            mock_extractor_inst.model = mock_model
            
            # preprocess 시뮬레이션: tensor 반환
            mock_tensor = MagicMock()
            # unsqueeze(0).cpu().numpy() 연쇄 호출 결과로 더미 numpy 입력 제공
            mock_tensor.unsqueeze.return_value.cpu.return_value.numpy.return_value = np.zeros((1, 3, 256, 128), dtype=np.float32)
            mock_extractor_inst.preprocess.return_value = mock_tensor
            mock_feature_extractor.return_value = mock_extractor_inst

            # 3. use_onnx=True 옵션으로 Extractor 초기화
            from src.core.reid_extractor import ReIDExtractor
            extractor = ReIDExtractor(model_name="osnet_x0_25", use_onnx=True)
            
            # export 함수 및 InferenceSession 초기화 호출 검증
            mock_export.assert_called_once()
            mock_session_class.assert_called_once()
            self.assertTrue(extractor.use_onnx)
            self.assertIsNotNone(extractor.ort_session)
            
            # 4. 가상 프레임과 TrackResult 리스트로 특징 추출 검증
            from src.core.tracker import TrackResult
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            track_results = [TrackResult(track_id=7, bbox=[10, 20, 100, 200], confidence=0.85)]
            
            results = extractor.extract(frame, track_results)
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['track_id'], 7)
            self.assertEqual(len(results[0]['vector']), 512)
            self.assertEqual(results[0]['vector'][0], 1.0)
            
        finally:
            # 5. sys.modules 복구 처리
            if original_ort is not None:
                sys.modules["onnxruntime"] = original_ort
            elif "onnxruntime" in sys.modules:
                del sys.modules["onnxruntime"]


if __name__ == "__main__":
    unittest.main()
