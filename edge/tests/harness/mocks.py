"""
mocks.py
--------
테스트용 Mock 클래스 모음.

실제 외부 의존성(Qdrant, YOLO, BoxMOT, OSNet, HTTP)을 사용하지 않고
파이프라인 로직을 격리하여 검증할 수 있도록 설계되었습니다.

각 Mock은 실제 클래스의 인터페이스(메서드 시그니처)를 그대로 따르되,
내부에서는 in-memory 자료구조만 사용합니다.
"""

import numpy as np
from typing import List, Optional

from tests.harness.fixtures import dummy_bgr_frame, dummy_reid_vector
from src.core.tracker import TrackResult


# ==========================================================================
# MockVectorDBClient
# ==========================================================================

class MockVectorDBClient:
    """VectorDBClient의 Mock 구현.

    실제 Qdrant 없이 in-memory dict에 벡터를 저장합니다.

    사용법:
        mock_db = MockVectorDBClient()
        mock_db.upsert('reid_collection', records)
        assert mock_db.upsert_call_count == 1
        assert 'reid_collection' in mock_db.store
    """

    def __init__(self, connect_should_fail: bool = False):
        # 저장소: {collection_name: [record, ...]}
        self.store: dict = {}
        self.connect_should_fail = connect_should_fail

        # 호출 추적
        self.upsert_call_count: int = 0
        self.search_call_count: int = 0
        self.connect_call_count: int = 0

    # --- VectorDBClient 인터페이스 구현 ---

    def connect(self, host=None, port=None, **kwargs) -> bool:
        self.connect_call_count += 1
        if self.connect_should_fail:
            raise ConnectionError("Mock: 의도적인 연결 실패")
        return True

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.store

    def ensure_collection(self, collection_name: str, vector_size: int = 512):
        if collection_name not in self.store:
            self.store[collection_name] = []

    def upsert(self, collection_name: str, records: list, vector_size: int = 512) -> bool:
        self.ensure_collection(collection_name, vector_size)
        self.store[collection_name].extend(records)
        self.upsert_call_count += 1
        return True

    def search(self, collection_name: str, query_vector: list, top_k: int = 10) -> dict:
        self.search_call_count += 1
        # 실제 유사도 계산 없이 저장된 레코드를 그대로 반환 (테스트용)
        stored = self.store.get(collection_name, [])
        hits = [
            {'id': r.get('id', idx), 'score': 1.0}
            for idx, r in enumerate(stored[:top_k])
        ]
        return {
            'hits': hits,
            'latency_ms': 0.1,
            'top_k': top_k,
            'hit_count': len(hits),
        }

    def index_exists(self, collection_name: str) -> bool:
        return self.collection_exists(collection_name)

    # --- 테스트 헬퍼 ---

    def get_records(self, collection_name: str) -> list:
        """저장된 레코드 전체 반환."""
        return self.store.get(collection_name, [])

    def total_record_count(self, collection_name: str) -> int:
        """저장된 레코드 수 반환."""
        return len(self.store.get(collection_name, []))

    def reset(self):
        """저장소와 호출 카운터 초기화 (여러 테스트 간 상태 격리용)."""
        self.store.clear()
        self.upsert_call_count = 0
        self.search_call_count = 0
        self.connect_call_count = 0


# ==========================================================================
# MockHTTPSender
# ==========================================================================

class MockHTTPSender:
    """서버 HTTP POST 전송의 Mock 구현.

    실제 FastAPI 서버 없이 전송된 페이로드를 in-memory 리스트에 기록합니다.

    사용법:
        sender = MockHTTPSender()
        sender.post('/api/v1/vectors', payload)
        assert sender.call_count == 1
        assert sender.last_payload['tracks'][0]['track_id'] == 7
    """

    def __init__(self, should_fail: bool = False, fail_after_n: int = None):
        """
        Args:
            should_fail: True이면 모든 요청이 실패합니다.
            fail_after_n: N번 성공 후 이후 요청을 실패로 만듭니다 (네트워크 불안정 시뮬레이션).
        """
        self.should_fail = should_fail
        self.fail_after_n = fail_after_n

        # 호출 기록
        self.sent_payloads: list = []   # 실제로 전송된 페이로드 목록
        self.failed_payloads: list = [] # 실패한 페이로드 목록
        self.call_count: int = 0

    def post(self, endpoint: str, payload: dict) -> tuple:
        """HTTP POST 요청을 시뮬레이션합니다.

        Returns:
            (status_code: int, response_body: dict)
        """
        self.call_count += 1

        # 실패 조건 확인
        should_fail_now = self.should_fail
        if self.fail_after_n is not None and self.call_count > self.fail_after_n:
            should_fail_now = True

        if should_fail_now:
            self.failed_payloads.append({'endpoint': endpoint, 'payload': payload})
            return 503, {'error': 'Mock: 서버 응답 없음'}

        self.sent_payloads.append({'endpoint': endpoint, 'payload': payload})
        return 200, {'status': 'ok', 'received': len(payload.get('tracks', []))}

    # --- 테스트 헬퍼 ---

    @property
    def last_payload(self) -> Optional[dict]:
        """마지막으로 성공 전송된 페이로드."""
        if not self.sent_payloads:
            return None
        return self.sent_payloads[-1]['payload']

    @property
    def last_endpoint(self) -> Optional[str]:
        """마지막으로 호출된 엔드포인트."""
        if not self.sent_payloads:
            return None
        return self.sent_payloads[-1]['endpoint']

    def reset(self):
        """호출 기록 초기화."""
        self.sent_payloads.clear()
        self.failed_payloads.clear()
        self.call_count = 0


# ==========================================================================
# MockDetector
# ==========================================================================

class MockDetectionResult:
    """DetectionResult의 최소 Mock (detector.py 의존성 격리용)."""

    def __init__(self, bbox, confidence=0.9, class_id=0):
        self.bbox = bbox
        self.confidence = confidence
        self.class_id = class_id
        self.label = 'person'

    def to_dict(self) -> dict:
        return {
            'bbox': self.bbox,
            'confidence': self.confidence,
            'class_id': self.class_id,
            'label': self.label,
        }


class MockDetector:
    """PersonDetector의 Mock 구현.

    실제 YOLOv8 모델 없이 고정된 탐지 결과를 반환합니다.

    사용법:
        detector = MockDetector(num_detections=2)
        results = detector.detect(frame)
        dets_np = detector.to_numpy(results)
    """

    is_loaded = True

    def __init__(self, num_detections: int = 2, confidence: float = 0.9):
        self.num_detections = num_detections
        self.confidence = confidence
        self.detect_call_count = 0

    def detect(self, frame) -> list:
        self.detect_call_count += 1
        return [
            MockDetectionResult(
                bbox=[50 + i * 100, 50, 150 + i * 100, 300],
                confidence=self.confidence,
            )
            for i in range(self.num_detections)
        ]

    def to_numpy(self, detections: list):
        if not detections:
            return np.empty((0, 6), dtype=np.float32)
        rows = []
        for d in detections:
            x1, y1, x2, y2 = d.bbox
            rows.append([x1, y1, x2, y2, d.confidence, d.class_id])
        return np.array(rows, dtype=np.float32)


# ==========================================================================
# MockTracker
# ==========================================================================

class MockTracker:
    """PersonTracker의 Mock 구현.

    실제 BoxMOT 없이 고정된 TrackResult 리스트를 반환합니다.

    사용법:
        tracker = MockTracker(track_ids=[1, 2, 3])
        tracks = tracker.update(dets_np, frame)
    """

    is_loaded = True

    def __init__(self, track_ids: List[int] = None):
        self.track_ids = track_ids if track_ids is not None else [1, 2]
        self.update_call_count = 0

    def update(self, dets: np.ndarray, frame: np.ndarray) -> List[TrackResult]:
        self.update_call_count += 1
        return [
            TrackResult(
                track_id=tid,
                bbox=[100 + tid * 50, 100, 200 + tid * 50, 350],
                confidence=0.88,
                class_id=0,
            )
            for tid in self.track_ids
        ]

    def reset(self):
        self.update_call_count = 0


# ==========================================================================
# MockReIDExtractor
# ==========================================================================

class MockReIDExtractor:
    """ReIDExtractor의 Mock 구현.

    실제 OSNet 모델 없이 랜덤 L2-정규화 벡터를 반환합니다.

    사용법:
        reid = MockReIDExtractor()
        vectors = reid.extract(frame, track_results)
        assert len(vectors) == len(track_results)
        assert len(vectors[0]['vector']) == 512
    """

    is_loaded = True

    def __init__(self, vector_dim: int = 512):
        self.vector_dim = vector_dim
        self.extract_call_count = 0

    def extract(self, frame, track_results: List[TrackResult]) -> List[dict]:
        self.extract_call_count += 1
        results = []
        for track in track_results:
            results.append({
                'track_id': track.track_id,
                'vector': dummy_reid_vector(self.vector_dim),
                'confidence': track.confidence,
                'bbox': track.bbox,
            })
        return results


# ==========================================================================
# MockYOLO
# ==========================================================================

class MockBox:
    """YOLO 박스 객체의 Mock 구현."""

    def __init__(self, xyxy, conf, cls):
        import torch
        self.xyxy = [torch.tensor(xyxy, dtype=torch.float32)]
        self.conf = [torch.tensor(conf, dtype=torch.float32)]
        self.cls = [torch.tensor(cls, dtype=torch.float32)]


class MockPredictionResult:
    """YOLO 예측 결과 객체의 Mock 구현."""

    def __init__(self, boxes: list):
        self.boxes = boxes


class MockYOLO:
    """ultralytics YOLO 모델의 Mock 구현."""

    def __init__(self, model_path: str = 'yolov8n.pt', *args, **kwargs):
        self.model_path = model_path
        self.exported = False

    def export(self, format: str = 'engine', **kwargs):
        self.exported = True
        # 가상으로 .engine 파일이 생성된 척 동작하도록 할 수 있음
        if self.model_path.endswith('.pt'):
            engine_path = self.model_path.replace('.pt', '.engine')
            with open(engine_path, 'w') as f:
                f.write('mock engine content')

    def predict(self, frame, conf: float = 0.5, classes: list = None, verbose: bool = False, **kwargs) -> list:
        # 2개의 모형 BBox 사람 객체 생성
        boxes = [
            MockBox(xyxy=[50.0, 50.0, 150.0, 300.0], conf=0.9, cls=0.0),
            MockBox(xyxy=[150.0, 50.0, 250.0, 300.0], conf=0.85, cls=0.0)
        ]
        return [MockPredictionResult(boxes=boxes)]

