"""
detector.py
-----------
YOLOv8 기반의 사람 객체 탐지(Person Detection) 모듈.
입력 비디오 프레임에서 사람 객체를 감지하고 바운딩 박스와 신뢰도를 추출합니다.
"""

import logging
from typing import List
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class DetectionResult:
    """단일 객체 탐지 결과 데이터 구조."""

    def __init__(self, bbox: List[int], confidence: float, class_id: int = 0):
        """
        Args:
            bbox: 바운딩 박스 좌표 [xmin, ymin, xmax, ymax]
            confidence: 탐지 신뢰도 (0.0 ~ 1.0)
            class_id: 클래스 식별자 (사람: 0)
        """
        self.bbox = [int(x) for x in bbox]
        self.confidence = float(confidence)
        self.class_id = int(class_id)
        self.label = 'person' if class_id == 0 else f'class_{class_id}'

    def to_dict(self) -> dict:
        """딕셔너리 포맷으로 변환 (직렬화용)."""
        return {
            'bbox': self.bbox,
            'confidence': self.confidence,
            'class_id': self.class_id,
            'label': self.label,
        }

    def __repr__(self):
        return f"DetectionResult(label={self.label}, bbox={self.bbox}, conf={self.confidence:.2f})"


class PersonDetector:
    """YOLOv8 사람 탐지 컴포넌트."""

    is_loaded = False

    def __init__(self, model_path: str = 'yolov8n.pt', conf_threshold: float = 0.5, use_tensorrt: bool = False):
        """
        Args:
            model_path: YOLOv8 가중치 파일 (.pt 또는 TensorRT .engine 파일 등)
            conf_threshold: 탐지 신뢰도 임계값 (이 값 이상의 결과만 반환)
            use_tensorrt: TensorRT 모듈 사용 여부 (향후 확장성을 위해 보존)
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.use_tensorrt = use_tensorrt
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """YOLOv8 모델을 로드하여 초기화합니다."""
        try:
            logger.info(f"Loading YOLO model from '{self.model_path}'...")
            self.model = YOLO(self.model_path)
            self.is_loaded = True
            logger.info("YOLO model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """입력 이미지 프레임에서 사람(class_id = 0)을 감지합니다.

        Args:
            frame: 입력 이미지 (BGR 형식 numpy array).

        Returns:
            감지된 사람들의 DetectionResult 리스트.
        """
        if not self.is_loaded or self.model is None:
            logger.warning("YOLO model not loaded. Returning empty detection list.")
            return []

        try:
            # predict 수행 (사람 클래스 0만 감지하고 싶지만 일단 전체 감지 후 필터링하거나 YOLO conf 설정을 따름)
            results = self.model.predict(
                frame,
                conf=self.conf_threshold,
                classes=[0],  # YOLO 내부적으로 0(person) 클래스만 출력하도록 필터링
                verbose=False
            )

            detections = []
            if len(results) > 0 and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    # xmin, ymin, xmax, ymax
                    bbox = [int(x) for x in box.xyxy[0].cpu().numpy()]
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())

                    detections.append(
                        DetectionResult(
                            bbox=bbox,
                            confidence=confidence,
                            class_id=class_id
                        )
                    )
            return detections
        except Exception as e:
            logger.error(f"Error during YOLO detection: {e}")
            return []

    def to_numpy(self, detections: List[DetectionResult]) -> np.ndarray:
        """DetectionResult 리스트를 추적기(BoxMOT) 입력에 적합한 (N, 6) NumPy float32 행렬로 변환합니다.

        포맷: [xmin, ymin, xmax, ymax, confidence, class_id]

        Args:
            detections: DetectionResult 객체 리스트.

        Returns:
            shape이 (N, 6)인 numpy array.
        """
        if not detections:
            return np.empty((0, 6), dtype=np.float32)

        rows = []
        for d in detections:
            xmin, ymin, xmax, ymax = d.bbox
            rows.append([xmin, ymin, xmax, ymax, d.confidence, d.class_id])
            
        return np.array(rows, dtype=np.float32)
