"""
reid_extractor.py
-----------------
OSNet 기반의 Re-Identification (Re-ID) 특징 추출 모듈.
추적 대상(사람)의 크롭 이미지 영역(ROI)으로부터 512차원 특징 벡터를 추출하여 고유의 신원 임베딩을 구성합니다.
"""

import logging
from typing import List, Dict
import cv2
import numpy as np
import torch

try:
    from torchreid.utils import FeatureExtractor
except ImportError:
    try:
        from torchreid.reid.utils import FeatureExtractor
    except ImportError:
        FeatureExtractor = None

from src.core.tracker import TrackResult

logger = logging.getLogger(__name__)


class ReIDExtractor:
    """OSNet Re-ID 특징 벡터 추출 컴포넌트."""

    is_loaded = False

    def __init__(self, model_name: str = 'osnet_x0_25'):
        """
        Args:
            model_name: 사용할 OSNet 모델 이름 (기본값: 'osnet_x0_25')
        """
        self.model_name = model_name
        self.extractor = None
        self._initialize_extractor()

    def _initialize_extractor(self):
        """FeatureExtractor를 로드하고 초기화합니다."""
        if FeatureExtractor is None:
            logger.error("torchreid library is not installed or FeatureExtractor cannot be imported.")
            self.is_loaded = False
            return

        try:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"Initializing Re-ID FeatureExtractor ({self.model_name}) on {device}...")
            # FeatureExtractor 생성
            self.extractor = FeatureExtractor(
                model_name=self.model_name,
                device=device,
                verbose=False
            )
            self.is_loaded = True
            logger.info("Re-ID FeatureExtractor loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Re-ID FeatureExtractor: {e}")
            self.is_loaded = False

    def extract(self, frame: np.ndarray, track_results: List[TrackResult]) -> List[Dict]:
        """현재 프레임과 추적 결과를 기반으로 각 대상의 Re-ID 특징 벡터를 추출합니다.

        Args:
            frame: 현재 프레임 이미지 (BGR 형식 numpy array).
            track_results: 현재 프레임에서 추적 성공한 인물들의 TrackResult 목록.

        Returns:
            각 추적 대상별 정보가 담긴 딕셔너리 리스트.
            [
                {
                    'track_id': int,
                    'vector': List[float], (512차원)
                    'confidence': float,
                    'bbox': List[int]
                },
                ...
            ]
        """
        if not self.is_loaded or self.extractor is None:
            logger.warning("ReID Extractor not loaded. Returning mock/empty vectors.")
            return []

        if not track_results:
            return []

        h, w = frame.shape[:2]
        results = []

        for track in track_results:
            x1, y1, x2, y2 = track.bbox

            # 바운딩 박스 이미지 영역 클리핑 예외 처리 (프레임 범위를 벗어나지 않도록 방지)
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))

            # 유효한 영역 크기 검증
            if x2 <= x1 or y2 <= y1:
                continue

            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            try:
                # 노트북 코드 규격 준수: (256, 128) 리사이즈 (가로 256, 세로 128)
                # torchreid FeatureExtractor 입력에 적절하게 크기 정규화 수행
                roi_resized = cv2.resize(roi, (256, 128))

                # 특징 추출 수행
                # FeatureExtractor는 단일 numpy 이미지(H, W, C) 혹은 이미지 리스트를 지원합니다.
                features = self.extractor(roi_resized)
                
                # 텐서로부터 피처 벡터를 numpy를 거쳐 파이썬 표준 float 리스트로 가공
                vector = features[0].cpu().numpy().tolist()

                # 혹시 L2 정규화가 필요한 경우 수동 처리 (일반적으로 Qdrant Cosine 유사도를 사용할 때 정규화 유용)
                # OSNet FeatureExtractor는 디폴트로 normalize가 True로 동작하여 정규화 상태로 출력됩니다.

                results.append({
                    'track_id': track.track_id,
                    'vector': vector,
                    'confidence': track.confidence,
                    'bbox': [x1, y1, x2, y2],
                })
            except Exception as e:
                logger.error(f"Failed to extract Re-ID features for track_id {track.track_id}: {e}")
                continue

        return results
