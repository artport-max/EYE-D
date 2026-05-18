"""
test_e2e_pipeline.py
--------------------
입력된 영상 ➔ 객체 탐지 ➔ 객체 추적 ➔ ROI 크롭 및 악조건 보정 전처리 ➔ Re-ID 임베딩 ➔ DB 패킷 생성
으로 이어지는 엣지 핵심 파이프라인의 종단간(End-to-End) 데이터 흐름 및 입출력 규격 무결성을 검증합니다.

리포지토리 표준 mocks.py의 Mock 컴포넌트들을 사용하여
실제 라이브러리 인터페이스 시그니처와 100% 동일하게 종단 연동 흐름을 검증합니다.
"""

import unittest
import numpy as np
import cv2
import time
from unittest.mock import MagicMock, patch

from src.core.pipeline_runner import PipelineRunner
from src.core.preprocessor import ImagePreprocessor
from src.core.tracker import TrackResult
from tests.harness.mocks import (
    MockDetector,
    MockTracker,
    MockReIDExtractor,
)

class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        # 1. 엣지 가상 BGR 입력 비디오 프레임 시뮬레이션 (360x640)
        # 중앙 부분에 다채로운 텍스처를 주어 보행자 객체를 모사합니다.
        self.frame = np.ones((360, 640, 3), dtype=np.uint8) * 40
        np.random.seed(99)
        pedestrian_texture = (np.random.rand(120, 60, 3) * 255).astype(np.uint8)
        self.frame[120:240, 290:350] = pedestrian_texture  # 프레임 중앙에 주입
        
        # 2. Vector DB 전송 가상 확인 큐
        self.db_client = MagicMock()
        self.db_records = []
        self.db_client.upsert = MagicMock(side_effect=lambda col, records: self.db_records.extend(records))

    def test_e2e_pipeline_data_flow_and_embedding_extraction(self):
        """[정상 흐름 E2E] 탐지 ➔ 추적 ➔ 전처리 ➔ ReID 임베딩의 연쇄 데이터 흐름이 단절 없이 도출되는지 검증합니다."""
        
        # 1. 리포지토리 표준 Mock 컴포넌트 로딩 및 팩토리 설정
        # 1개의 탐지 대상 및 track_id=1을 부여하도록 셋업
        detector = MockDetector(num_detections=1)
        tracker = MockTracker(track_ids=[1])
        reid = MockReIDExtractor(vector_dim=512)
        
        # 2. E2E 파이프라인 러너 기동
        runner = PipelineRunner(config={
            'collection_name': 'e2e_test_collection',
            'use_onnx': False
        }, db_client=self.db_client)
        
        # 모킹된 공식 인터페이스 인스턴스 강제 주입
        runner._detector = detector
        runner._tracker = tracker
        runner._reid = reid
        runner.running = True
        
        # 3. 단일 프레임 파이프라인 실행
        result = runner.process_frame(self.frame, camera_id="cam_east_01")
        
        # 4. 연쇄 결과물 무결성 검증
        self.assertIsNotNone(result)
        self.assertEqual(result['camera_id'], "cam_east_01")
        self.assertEqual(result['frame_index'], 1)
        
        # 탐지 및 트랙 개수 검증
        self.assertEqual(len(result['detections']), 1)
        self.assertEqual(len(result['tracks']), 1)
        self.assertEqual(result['tracks'][0]['track_id'], 1)
        
        # Re-ID 512차원 임베딩 생성 결과 확인
        self.assertEqual(len(result['reid_vectors']), 1)
        reid_record = result['reid_vectors'][0]
        self.assertEqual(reid_record['track_id'], 1)
        self.assertEqual(len(reid_record['vector']), 512)
        self.assertIsInstance(reid_record['vector'][0], float)
        
        # 5. 최종 데이터베이스 전송 패킷 구조 무결성 검증
        self.assertEqual(self.db_client.upsert.call_count, 1)
        self.assertEqual(len(self.db_records), 1)
        
        saved_db_packet = self.db_records[0]
        self.assertIn('id', saved_db_packet)
        self.assertEqual(len(saved_db_packet['vector']), 512)
        self.assertEqual(saved_db_packet['payload']['camera_id'], "cam_east_01")
        self.assertEqual(saved_db_packet['payload']['track_id'], 1)
        self.assertIn('timestamp', saved_db_packet['payload'])
        
        print("[✔] E2E 표준 파이프라인 통합 데이터 연쇄 테스트 완벽 통과!")

    def test_e2e_pipeline_harsh_conditions_adaptation(self):
        """[악조건 복원력 E2E] 야간/역광 악조건 프레임 투입 시, 전처리기가 자동 적용되어 특징을 정상 추출하는지 검증합니다."""
        
        # 1. 극도로 어두운 암흑 야간 프레임(평균 밝기 15) 생성
        night_frame = np.ones((360, 640, 3), dtype=np.uint8) * 15
        # 중심부에 어두운 보행자 실루엣 그리기
        night_frame[120:240, 290:350] = 12
        
        # 2. 모킹된 컴포넌트 셋업 (표준 인터페이스 적용)
        detector = MockDetector(num_detections=1)
        tracker = MockTracker(track_ids=[99]) # track_id 99 부여
        
        # Re-ID 측에서 실제 2개 인수를 받아 통과하는 훅 설정
        captured_rois = []
        def extract_hook(frame, track_results):
            h, w = frame.shape[:2]
            for track in track_results:
                x1, y1, x2, y2 = track.bbox
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                if x2 > x1 and y2 > y1:
                    roi = frame[y1:y2, x1:x2]
                    # 실제 ReIDExtractor.extract 내부에서 enhance_roi 가 호출되므로
                    # 이 테스트에서는 preprocessor가 night_frame에 가한 효과와 ROI 선명화 효과를 동시에 캡처합니다.
                    enhanced_roi = runner.preprocessor.enhance_roi(roi)
                    captured_rois.append(enhanced_roi)
            
            # MockReIDExtractor 표준 리턴 형식과 매칭
            return [
                {
                    'track_id': track.track_id,
                    'vector': [0.0] * 512,
                    'confidence': track.confidence,
                    'bbox': track.bbox
                }
                for track in track_results
            ]
            
        reid = MockReIDExtractor(vector_dim=512)
        reid.extract = MagicMock(side_effect=extract_hook)
        
        # 3. 파이프라인 러너 기동
        runner = PipelineRunner(db_client=self.db_client)
        runner._detector = detector
        runner._tracker = tracker
        runner._reid = reid
        runner.running = True
        
        # 4. 야간 조도 모드(is_night) 시뮬레이션 하에 프레임 처리
        # PipelineRunner.process_frame() 내부에서 self.preprocessor.process(frame)가 실행됩니다.
        # 강제로 runner의 preprocessor가 이 프레임을 야간 상황으로 보정하도록 테스트 상황 유도
        original_process = runner.preprocessor.process
        def process_night_hook(img, is_night=False, is_backlit=False):
            # E2E 야간 시뮬레이션을 위해 is_night=True 강제 주입
            return original_process(img, is_night=True, is_backlit=is_backlit)
            
        runner.preprocessor.process = MagicMock(side_effect=process_night_hook)
        
        # E2E 파이프라인 실행
        result = runner.process_frame(night_frame, camera_id="cam_night_e2e")
        
        # 5. 연쇄 보정 결과 검증
        self.assertIsNotNone(result)
        self.assertEqual(len(captured_rois), 1)
        
        processed_roi = captured_rois[0]
        original_roi_avg = 12.0
        processed_roi_avg = np.mean(processed_roi)
        
        # 야간 감마 1.6 보정에 의해 픽셀 조도가 극단적인 12.0에서 유의미하게 상승했는지 검증
        self.assertGreater(processed_roi_avg, original_roi_avg)
        self.assertGreater(processed_roi_avg, 35.0)  
        
        # Re-ID 임베딩 결과 전송 큐 규격 검증
        self.assertEqual(len(result['reid_vectors']), 1)
        self.assertEqual(result['reid_vectors'][0]['track_id'], 99)
        self.assertEqual(len(result['reid_vectors'][0]['vector']), 512)
        
        print(f"[✔] 악조건 E2E 보정 복원 연쇄 성공! (보정 전 조도: {original_roi_avg:.1f} ➔ 보정 후 조도: {processed_roi_avg:.1f})")

if __name__ == "__main__":
    unittest.main()
