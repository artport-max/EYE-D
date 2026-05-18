import numpy as np
from src.core.tracker import TrackResult

def dummy_bgr_frame(width=640, height=480):
    """테스트용 더미 BGR 프레임 생성 (검은색 배경에 간단한 사각형)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # 중앙에 흰색 사각형 하나 그림
    frame[height//4:3*height//4, width//4:3*width//4] = 255
    return frame

def dummy_track_results():
    """테스트용 더미 TrackResult 리스트 생성."""
    return [
        TrackResult(track_id=1, bbox=[100, 100, 200, 300], confidence=0.9, class_id=0),
        TrackResult(track_id=2, bbox=[300, 150, 450, 400], confidence=0.85, class_id=0)
    ]

def dummy_reid_vector(dim=512):
    """테스트용 더미 Re-ID 벡터 생성 (L2 정규화된 랜덤 벡터)."""
    vec = np.random.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()
