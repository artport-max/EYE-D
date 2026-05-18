import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """실환경 악조건(역광, 야간 저조도, 저해상도)에 대응하기 위한 프레임 및 인물 ROI 전처리 보정 모듈."""

    def __init__(self, use_awb=True, use_blur=True, blur_kernel=(3, 3), use_gamma=True, gamma=1.2, use_sharpen=True):
        """
        Args:
            use_awb: LAB 영역 CLAHE 기반 자동 조도 및 화이트밸런스 적용 여부
            use_blur: 노이즈 감쇄용 Gaussian Blur 적용 여부
            blur_kernel: 가우시안 블러 커널 사이즈
            use_gamma: 저조도(야간) 대응 감마 보정 적용 여부
            gamma: 감마 보정 계수 (1.0 초과: 밝게 보정, 1.0 미만: 어둡게 보정)
            use_sharpen: 저해상도 대응 적응형 선명화(Sharpening) 적용 여부
        """
        self.use_awb = use_awb
        self.use_blur = use_blur
        self.blur_kernel = blur_kernel
        self.use_gamma = use_gamma
        self.gamma = gamma
        self.use_sharpen = use_sharpen
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization) 객체 초기화 (역광/조도 대비 극대화)
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        
        # 감마 변환용 Lookup Table(LUT) 사전 빌드 (성능 최적화)
        self.gamma_lut = self._build_gamma_lut(self.gamma)

    def _build_gamma_lut(self, gamma):
        """감마 계수를 기반으로 8비트 그레이스케일 매핑용 LUT 테이블을 고속 빌드합니다."""
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        return table

    def process(self, frame, is_night=False, is_backlit=False):
        """
        입력 프레임 전체에 대해 실환경 조도 및 노이즈 보정을 적용합니다.
        
        Args:
            frame: BGR 형식의 프레임 이미지
            is_night: 야간/저조도 모드 여부 (감마 보정 강도 상향 및 노이즈 억제 최적화)
            is_backlit: 역광 모드 여부 (CLAHE 대비 보정 수치 극대화)
        """
        if frame is None:
            return None

        processed_frame = frame.copy()

        try:
            # 1. 노이즈 제거 (야간인 경우 미세 블러를 강하게 주어 센서 노이즈를 억제)
            if self.use_blur:
                kernel = (5, 5) if is_night else self.blur_kernel
                processed_frame = cv2.GaussianBlur(processed_frame, kernel, 0)

            # 2. 감마 보정 (야간/저조도 상황일 때 밝기 스케일을 자연스럽게 상향)
            if self.use_gamma or is_night:
                active_lut = self.gamma_lut
                if is_night and self.gamma == 1.2:
                    # 야간인 경우 특수 감마 LUT 생성 (더 밝게 보정)
                    active_lut = self._build_gamma_lut(1.6)
                processed_frame = cv2.LUT(processed_frame, active_lut)

            # 3. 역광 및 광량 불균일 보정 (CLAHE 대비 보정 기법)
            if self.use_awb or is_backlit:
                lab = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                
                # 역광 상황에서는 CLAHE 강도(clipLimit)를 동적으로 극대화하여 어두운 부분 인물 윤곽 활성화
                if is_backlit:
                    temp_clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
                    cl = temp_clahe.apply(l)
                else:
                    cl = self.clahe.apply(l)
                    
                limg = cv2.merge((cl, a, b))
                processed_frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
                
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}")
            return frame # 예외 시 안전하게 원본 프레임 반환

        return processed_frame

    def enhance_roi(self, roi):
        """
        탐지된 인물의 크롭 이미지(ROI)에 대해 저해상도 뭉개짐을 완화하기 위한 특수 전처리(Sharpening)를 수행합니다.
        Re-ID 모델에 크롭 이미지를 넣기 전에 윤곽 테두리와 질감(Texture) 디테일을 극대화합니다.
        """
        if roi is None or roi.size == 0:
            return roi

        try:
            # 1. 이미지 선명도 강화를 위한 적응형 언샤프 마스킹(Unsharp Masking) 기법 적용
            if self.use_sharpen:
                gaussian = cv2.GaussianBlur(roi, (3, 3), 0)
                # 원본 이미지에서 블러 처리된 차분(Detail)을 강조하여 합성
                sharpened = cv2.addWeighted(roi, 1.5, gaussian, -0.5, 0)
                return sharpened
        except Exception as e:
            logger.warning(f"ROI enhancement failed: {e}")
            
        return roi

    def normalize_for_model(self, frame, input_size=(640, 640)):
        """YOLOv8 모델 및 TensorRT 엔진 입력 호환용 정규화"""
        resized = cv2.resize(frame, input_size)
        normalized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB) / 255.0
        return normalized.astype(np.float32)
