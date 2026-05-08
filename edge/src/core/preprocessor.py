import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """Preprocesses input frames for detection and Re-ID models."""

    def __init__(self, use_awb=True, use_blur=True, blur_kernel=(3, 3)):
        self.use_awb = use_awb
        self.use_blur = use_blur
        self.blur_kernel = blur_kernel
        
        # simple white balance based on gray world assumption or CLAHE
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def process(self, frame):
        """
        Applies preprocessing steps to the input frame.
        """
        if frame is None:
            return None

        processed_frame = frame.copy()

        try:
            # 1. Noise Reduction (Gaussian Blur)
            if self.use_blur:
                processed_frame = cv2.GaussianBlur(processed_frame, self.blur_kernel, 0)

            # 2. Illumination Correction / Auto White Balance (using CLAHE on L channel of LAB)
            if self.use_awb:
                lab = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                cl = self.clahe.apply(l)
                limg = cv2.merge((cl, a, b))
                processed_frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
                
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}")
            return frame # Fallback to original frame if preprocessing fails

        return processed_frame

    def normalize_for_model(self, frame, input_size=(640, 640)):
        """
        Resize and normalize frame for standard model input if needed.
        Note: YOLO models often handle normalization internally via ultralytics,
        but this method is kept for manual handling if required by TensorRT engines.
        """
        resized = cv2.resize(frame, input_size)
        # convert to RGB, normalize to [0, 1]
        normalized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB) / 255.0
        return normalized.astype(np.float32)
