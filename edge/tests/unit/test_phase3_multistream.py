import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import time

class TestMultiStreamPipeline(unittest.TestCase):
    """MultiStreamPipelineRunner의 다중 채널 비동기 처리 및 자원 공유 동작을 검증합니다."""

    @patch("src.core.pipeline_runner.PipelineRunner")
    @patch("cv2.VideoCapture")
    def test_multistream_pipeline_running_and_sharing(self, mock_video_capture, mock_pipeline_runner_class):
        """다중 RTSP/카메라 입력이 들어왔을 때, 모델 공유 기반으로 무결하게 기동하고 비동기로 분배 추론이 수행되는지 검증합니다."""
        
        # 1. PipelineRunner Mocking 설정
        mock_runner_inst = MagicMock()
        mock_pipeline_runner_class.return_value = mock_runner_inst
        mock_runner_inst.start.return_value = True
        mock_runner_inst.stop.return_value = True
        mock_runner_inst.frames_processed = 0
        
        # process_frame이 호출될 때마다 더미 결과 반환
        def dummy_process_frame(frame, camera_id):
            mock_runner_inst.frames_processed += 1
            return {
                'frame_index': mock_runner_inst.frames_processed,
                'camera_id': camera_id,
                'reid_vectors': [{'track_id': 1, 'vector': [0.1] * 512}],
                'processing_time_ms': 5.0
            }
        mock_runner_inst.process_frame.side_effect = dummy_process_frame
        
        # 2. cv2.VideoCapture Mocking 설정
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        # 프레임을 무사히 리드할 수 있도록 더미 프레임 반환
        mock_cap.read.return_value = (True, np.zeros((240, 320, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap
        
        # 3. MultiStreamPipelineRunner 생성 및 기동
        from src.core.pipeline_runner import MultiStreamPipelineRunner
        
        sources = {
            "cam_0": "rtsp://192.168.1.100/stream1",
            "cam_1": "rtsp://192.168.1.101/stream2"
        }
        
        runner = MultiStreamPipelineRunner(
            sources=sources,
            config={'use_onnx': True},
            queue_size=10
        )
        
        # 캡처를 열었을 때 정상 기동 검증
        start_success = runner.start()
        self.assertTrue(start_success)
        self.assertTrue(runner.running)
        self.assertEqual(len(runner.caps), 2)
        
        # 두 스레드가 비동기로 큐에 프레임을 집어넣고, 워커가 추론하는 시간을 고려해 대기
        time.sleep(0.5)
        
        status = runner.get_status()
        self.assertTrue(status['running'])
        self.assertIn("cam_0", status['active_streams'])
        self.assertIn("cam_1", status['active_streams'])
        
        # 결과 큐에서 비동기로 분석 완료 리포트가 채널별로 정상 적재되었는지 획득 검증
        res_list = []
        for _ in range(5):
            res = runner.get_next_result(timeout=0.1)
            if res:
                res_list.append(res)
                
        self.assertGreater(len(res_list), 0)
        # 획득한 리포트의 구조 무결성 검증
        sample = res_list[0]
        self.assertIn('camera_id', sample)
        self.assertIn('reid_vectors', sample)
        self.assertEqual(len(sample['reid_vectors'][0]['vector']), 512)
        
        # 4. 자원 해제 및 정지 검증
        stop_success = runner.stop()
        self.assertTrue(stop_success)
        self.assertFalse(runner.running)

if __name__ == "__main__":
    unittest.main()
