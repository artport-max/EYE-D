import logging
import time
import os

import cv2
import numpy as np

from src.core.preprocessor import ImagePreprocessor

logger = logging.getLogger(__name__)


class PipelineRunner:
    """DeepStream / YOLO / ByteTrack / Re-ID pipeline runner."""

    def __init__(self, config=None, db_client=None):
        self.config = config or {}
        self.running = False
        self.frames_processed = 0

        # 모델 및 모듈 초기화
        self.yolo_model = None
        self.tracker = None
        self.reid_model = None
        self.preprocessor = ImagePreprocessor(use_awb=True, use_blur=True)
        self.db_client = db_client
        self.collection_name = self.config.get('collection_name', 'reid_collection')

    def start(self):
        self.running = True
        self.frames_processed = 0
        logger.info('Pipeline started')
        self._initialize_models()
        return True

    def stop(self):
        self.running = False
        logger.info('Pipeline stopped')
        return True

    def _initialize_models(self):
        """모델 초기화 - 실제 구현에서는 가중치 파일 로드."""
        try:
            self.yolo_model = self._load_yolo_model()
            self.tracker = self._initialize_tracker()
            self.reid_model = self._load_reid_model()
            logger.info('Models initialized successfully')
        except Exception as e:
            logger.error(f'Model initialization failed: {e}')

    def _load_yolo_model(self):
        """YOLOv8 모델 로드 및 TensorRT 최적화 지원."""
        try:
            from ultralytics import YOLO
            engine_path = 'yolov8n.engine'
            pt_path = 'yolov8n.pt'

            if os.path.exists(engine_path):
                model = YOLO(engine_path, task='detect')
                logger.info("Loaded YOLOv8 TensorRT engine.")
            else:
                model = YOLO(pt_path)
                if self.config.get('use_tensorrt', False):
                    logger.info("Exporting YOLO to TensorRT engine...")
                    model.export(format='engine', half=True)
                    if os.path.exists(engine_path):
                        model = YOLO(engine_path, task='detect')
                        logger.info("Exported and loaded TensorRT engine.")
            return model
        except ImportError:
            logger.warning('ultralytics not installed, using mock YOLO')
            from tests.harness.mocks import MockYOLOModel
            return MockYOLOModel()
        except Exception as e:
            logger.warning(f'Failed to load YOLO: {e}, using mock')
            from tests.harness.mocks import MockYOLOModel
            return MockYOLOModel()

    def _initialize_tracker(self):
        """ByteTrack 초기화."""
        try:
            from boxmot import BoxMOT
            tracker = BoxMOT(model_name='osnet_x0_25', device='cpu')
            return tracker
        except ImportError:
            logger.warning('boxmot not installed, using mock tracker')
            from tests.harness.mocks import MockByteTrack
            return MockByteTrack()
        except Exception as e:
            logger.warning(f'Failed to initialize tracker: {e}, using mock')
            from tests.harness.mocks import MockByteTrack
            return MockByteTrack()

    def _load_reid_model(self):
        """OSNet-light Re-ID 모델 로드."""
        try:
            from torchreid.utils import FeatureExtractor
            extractor = FeatureExtractor(model_name='osnet_x0_25', device='cpu')
            return extractor
        except ImportError:
            logger.warning('torchreid not installed, using mock Re-ID')
            from tests.harness.mocks import MockReidModel
            return MockReidModel()
        except Exception as e:
            logger.warning(f'Failed to load Re-ID model: {e}, using mock')
            from tests.harness.mocks import MockReidModel
            return MockReidModel()

    def process_frame(self, frame, camera_id="cam_0"):
        if not self.running or frame is None:
            return None

        start_time = time.time()

        processed_frame = self.preprocessor.process(frame)

        detections = self.detect_people(processed_frame)
        tracks = self.track_people(processed_frame, detections)
        reid_vectors = self.extract_reid_vectors(processed_frame, tracks, camera_id=camera_id)

        self.frames_processed += 1
        elapsed = time.time() - start_time

        return {
            'frame_index': self.frames_processed,
            'camera_id': camera_id,
            'detections': detections,
            'tracks': tracks,
            'reid_vectors': reid_vectors,
            'processing_time_ms': elapsed * 1000,
        }

    def process_batch(self, frames_dict):
        results = {}
        for channel_id, frame in frames_dict.items():
            if frame is not None:
                results[channel_id] = self.process_frame(frame, camera_id=channel_id)
            else:
                results[channel_id] = None
        return results

    def detect_people(self, frame):
        """YOLO를 사용한 사람 탐지."""
        if self.yolo_model is None:
            return []

        try:
            results = self.yolo_model(frame, conf=0.5, classes=0)
            detections = []
            for result in results:
                for box in result.boxes:
                    if box.conf[0] > 0.5:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detections.append({
                            'bbox': [x1, y1, x2, y2],
                            'confidence': float(box.conf[0]),
                            'class_id': 0,
                            'label': 'person',
                        })
            return detections
        except Exception as e:
            logger.warning(f'Detection failed: {e}')
            return []

    def track_people(self, frame, detections):
        """ByteTrack을 사용한 추적."""
        if self.tracker is None or not detections:
            return []

        try:
            bboxes = np.array([[d['bbox'][0], d['bbox'][1], d['bbox'][2], d['bbox'][3], d['confidence']]
                               for d in detections], dtype=np.float32)

            if len(bboxes) == 0:
                return []

            tracks = self.tracker.update(bboxes, frame)
            result_tracks = []
            for track in tracks:
                x1, y1, x2, y2, track_id, conf = track[:6]
                result_tracks.append({
                    'track_id': int(track_id),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': float(conf),
                    'label': 'person',
                })
            return result_tracks
        except Exception as e:
            logger.warning(f'Tracking failed: {e}')
            return []

    def extract_reid_vectors(self, frame, tracks, camera_id="cam_0"):
        """OSNet-light을 사용한 Re-ID 벡터 추출 및 DB 저장."""
        if self.reid_model is None or not tracks:
            return []

        vectors = []
        db_records = []
        try:
            for track in tracks:
                x1, y1, x2, y2 = track['bbox']
                roi = frame[y1:y2, x1:x2]

                if roi.size == 0:
                    continue

                roi_resized = cv2.resize(roi, (256, 128))
                vector = self.reid_model(roi_resized)

                if isinstance(vector, np.ndarray):
                    vector = vector.flatten().tolist()
                elif hasattr(vector, 'tolist'):
                    vector = vector.tolist()

                vector_data = {
                    'track_id': track['track_id'],
                    'vector': vector,
                    'confidence': track['confidence'],
                }
                vectors.append(vector_data)
                
                db_records.append({
                    'id': hash(f"{camera_id}_{track['track_id']}_{time.time()}") % (10**8),
                    'vector': vector,
                    'payload': {
                        'camera_id': camera_id,
                        'track_id': track['track_id'],
                        'timestamp': time.time(),
                        'confidence': track['confidence']
                    }
                })

            if self.db_client is not None and db_records:
                try:
                    self.db_client.validate_insert(self.collection_name, db_records)
                except Exception as db_e:
                    logger.warning(f'Vector DB insert failed: {db_e}')

            return vectors
        except Exception as e:
            logger.warning(f'Re-ID extraction failed: {e}')
            return []

    def get_intermediate_results(self):
        return {
            'frames_processed': self.frames_processed,
            'yolo_loaded': self.yolo_model is not None,
            'tracker_loaded': self.tracker is not None,
            'reid_loaded': self.reid_model is not None,
        }

    def flush(self):
        return True



