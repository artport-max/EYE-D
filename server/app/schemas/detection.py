from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DetectionIn(BaseModel):
    """엣지(Jetson)에서 보내는 탐지 이벤트 페이로드."""

    # --- kote 본 용도 (필수) ---
    camera_id: str = Field(..., examples=["CAM_01"])
    tracklet_id: str = Field(..., description="엣지 내 임시 ID")
    embedding_identity: list[float] = Field(
        ..., description="OSNet 임베딩 (보통 512차원)"
    )
    timestamp: datetime
    bbox: list[float] = Field(..., description="[x1, y1, x2, y2]")
    event_type: str = Field(default="detection", examples=["detection", "intrusion"])

    # --- arttrace 확장 슬롯 (옵션, kote 기간엔 null 허용) ---
    pose_keypoints: Optional[list[list[float]]] = None
    action_label: Optional[str] = None
    dwell_seconds: Optional[float] = None
    appearance_attrs: Optional[dict] = None
    scene_context: Optional[dict] = None


class DetectionOut(BaseModel):
    """탐지 이벤트 처리 결과."""
    detection_id: int
    global_id: Optional[int] = None
    matched: bool
    similarity: Optional[float] = None