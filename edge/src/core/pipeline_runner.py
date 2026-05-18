"""
pipeline_runner.py
------------------
Re-ID 파이프라인 오케스트레이터.
detector.py, tracker.py, reid_extractor.py를 조립하여 전체 흐름을 제어합니다.

역할 분리:
  - PersonDetector   (detector.py)      : YOLOv8 탐지 전담
  - PersonTracker    (tracker.py)       : BoxMOT 추적 전담
  - ReIDExtractor    (reid_extractor.py): OSNet Re-ID 특징 추출 전담
  - PipelineRunner   (본 파일)          : 위 세 모듈 + DB 저장을 조립하는 오케스트레이터
"""

import logging
import time

from src.core.preprocessor import ImagePreprocessor
from src.core.detector import PersonDetector
from src.core.tracker import PersonTracker
from src.core.reid_extractor import ReIDExtractor
from src.infrastructure.null_objects import NullDBClient, NullSender

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Re-ID 파이프라인 오케스트레이터.

    각 컴포넌트(detector, tracker, reid_extractor)를 조립하여
    단일 프레임 또는 다중 채널 배치를 처리합니다.

    Usage:
        runner = PipelineRunner(config={'tracker_type': 'botsort'})
        runner.start()
        result = runner.process_frame(frame, camera_id='cam_0')
        runner.stop()
    """

    def __init__(self, config: dict = None, db_client=None, http_sender=None):
        """
        Args:
            config: 파이프라인 설정 딕셔너리.
                - yolo_model      (str)  : YOLO 모델 경로 (기본: 'yolov8n.pt')
                - conf_threshold  (float): 탐지 신뢰도 임계값 (기본: 0.5)
                - use_tensorrt    (bool) : TensorRT 변환 여부 (기본: False)
                - tracker_type    (str)  : 추적기 종류 (기본: 'botsort')
                - reid_weights    (str)  : Re-ID 가중치 파일 (기본: 'osnet_x0_25_msmt17.pt')
                - reid_model      (str)  : Re-ID 모델 이름 (기본: 'osnet_x0_25')
                - collection_name (str)  : 벡터 DB 컬렉션 이름 (기본: 'reid_collection')
            db_client: VectorDBClient 인스턴스.
                       None이면 NullDBClient(로그만 출력)가 자동으로 사용됩니다.
            http_sender: ServerSender 인스턴스 (Phase 3에서 주입).
                         None이면 NullSender(로그만 출력)가 자동으로 사용됩니다.
        """
        self.config = config or {}
        self.running = False
        self.frames_processed = 0

        self.preprocessor = ImagePreprocessor(use_awb=True, use_blur=True)
        # Null Object 패턴: None 대신 기본 Null 객체를 사용하여 None 체크 제거
        self.db_client = db_client if db_client is not None else NullDBClient()
        self.http_sender = http_sender if http_sender is not None else NullSender()
        self.collection_name = self.config.get('collection_name', 'reid_collection')

        # 각 컴포넌트는 start() 시점에 초기화
        self._detector: PersonDetector = None
        self._tracker: PersonTracker = None
        self._reid: ReIDExtractor = None

    # ------------------------------------------------------------------
    # 생명주기
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """파이프라인을 시작하고 모든 모델을 초기화합니다."""
        self.running = True
        self.frames_processed = 0
        logger.info('Pipeline starting...')
        self._initialize_models()
        logger.info('Pipeline started.')
        return True

    def stop(self) -> bool:
        """파이프라인을 종료합니다."""
        self.running = False
        logger.info('Pipeline stopped.')
        return True

    def _initialize_models(self):
        """detector, tracker, reid_extractor를 순서대로 초기화합니다."""
        try:
            self._detector = PersonDetector(
                model_path=self.config.get('yolo_model', 'yolov8n.pt'),
                conf_threshold=self.config.get('conf_threshold', 0.5),
                use_tensorrt=self.config.get('use_tensorrt', False),
            )
            logger.info(f"Detector initialized (model={self.config.get('yolo_model', 'yolov8n.pt')})")

            self._tracker = PersonTracker(
                tracker_type=self.config.get('tracker_type', 'botsort'),
                reid_weights=self.config.get('reid_weights', 'osnet_x0_25_msmt17.pt'),
            )
            logger.info(f"Tracker initialized (type={self.config.get('tracker_type', 'botsort')})")

            self._reid = ReIDExtractor(
                model_name=self.config.get('reid_model', 'osnet_x0_25'),
            )
            logger.info(f"ReID Extractor initialized (model={self.config.get('reid_model', 'osnet_x0_25')})")

        except Exception as e:
            logger.error(f'Model initialization failed: {e}')
            raise

    # ------------------------------------------------------------------
    # 프레임 처리 (오케스트레이션)
    # ------------------------------------------------------------------

    def process_frame(self, frame, camera_id: str = "cam_0") -> dict:
        """단일 프레임의 전체 파이프라인을 실행합니다.

        흐름: 전처리 → 탐지 → 추적 → Re-ID 추출 → DB 저장

        Args:
            frame: BGR 형식의 numpy 배열.
            camera_id: 카메라 식별자 (DB 페이로드에 기록됨).

        Returns:
            {
                'frame_index': int,
                'camera_id': str,
                'detections': List[dict],
                'tracks': List[dict],
                'reid_vectors': List[dict],
                'processing_time_ms': float,
            }
        """
        if not self.running or frame is None:
            return None

        start_time = time.time()

        # 1. 전처리
        processed_frame = self.preprocessor.process(frame)

        # 2. 탐지 (PersonDetector)
        det_results = self._detector.detect(processed_frame)
        dets_np = self._detector.to_numpy(det_results)   # (N, 6)

        # 3. 추적 (PersonTracker)
        track_results = self._tracker.update(dets_np, processed_frame)

        # 4. Re-ID 특징 추출 (ReIDExtractor)
        reid_vectors = self._reid.extract(processed_frame, track_results)

        # 5. 벡터 DB 저장
        self._save_to_db(reid_vectors, camera_id)

        # 6. 서버 전송 (Phase 3: ServerSender 주입 시 실제 동작, 미주입 시 NullSender)
        self._send_to_server(reid_vectors, camera_id)

        self.frames_processed += 1

        return {
            'frame_index': self.frames_processed,
            'camera_id': camera_id,
            'detections': [d.to_dict() for d in det_results],
            'tracks': [t.to_dict() for t in track_results],
            'reid_vectors': reid_vectors,
            'processing_time_ms': (time.time() - start_time) * 1000,
        }

    def process_batch(self, frames_dict: dict) -> dict:
        """다중 채널 프레임을 순차 처리합니다.

        Args:
            frames_dict: {camera_id: frame} 형태의 딕셔너리.

        Returns:
            {camera_id: process_frame 결과} 딕셔너리.
        """
        return {
            channel_id: self.process_frame(frame, camera_id=channel_id)
            if frame is not None else None
            for channel_id, frame in frames_dict.items()
        }

    def _save_to_db(self, reid_vectors: list, camera_id: str):
        """Re-ID 벡터를 DB에 저장합니다.

        db_client가 NullDBClient인 경우 저장을 건너뜁니다(로그만 출력).
        """
        if not reid_vectors:
            return

        db_records = [
            {
                'id': hash(f"{camera_id}_{v['track_id']}_{time.time()}") % (10 ** 8),
                'vector': v['vector'],
                'payload': {
                    'camera_id': camera_id,
                    'track_id': v['track_id'],
                    'timestamp': time.time(),
                    'confidence': v['confidence'],
                },
            }
            for v in reid_vectors
        ]

        try:
            self.db_client.upsert(self.collection_name, db_records)
        except Exception as e:
            logger.warning(f'Vector DB upsert failed: {e}')

    def _send_to_server(self, reid_vectors: list, camera_id: str):
        """Re-ID 벡터를 서버로 HTTP POST 전송합니다.

        http_sender가 NullSender인 경우 전송을 건너뜁니다(로그만 출력).
        Phase 3에서 ServerSender를 주입하면 실제 전송이 동작합니다.
        """
        if not reid_vectors:
            return

        payload = {
            'camera_id': camera_id,
            'timestamp': time.time(),
            'frame_index': self.frames_processed,
            'tracks': [
                {
                    'track_id': v['track_id'],
                    'vector': v['vector'],
                    'confidence': v.get('confidence', 0.0),
                    'bbox': v.get('bbox', []),
                }
                for v in reid_vectors
            ],
        }

        try:
            status_code, _ = self.http_sender.post('/api/v1/vectors', payload)
            if status_code not in (0, 200):
                logger.warning(
                    f'Server POST failed (status={status_code}): '
                    f'{len(reid_vectors)} vector(s) for camera {camera_id}'
                )
        except Exception as e:
            logger.warning(f'Server send error: {e}')

    # ------------------------------------------------------------------
    # 상태 조회
    # ------------------------------------------------------------------

    def get_intermediate_results(self) -> dict:
        """각 컴포넌트의 로드 상태를 반환합니다."""
        return {
            'frames_processed': self.frames_processed,
            'detector_loaded': self._detector is not None and self._detector.is_loaded,
            'tracker_loaded': self._tracker is not None and self._tracker.is_loaded,
            'reid_loaded': self._reid is not None and self._reid.is_loaded,
            'db_configured': type(self.db_client).__name__ != 'NullDBClient',
            'sender_configured': type(self.http_sender).__name__ != 'NullSender',
        }

    def flush(self) -> bool:
        return True

