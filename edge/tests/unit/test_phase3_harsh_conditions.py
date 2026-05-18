import unittest
import cv2
import numpy as np
from src.core.preprocessor import ImagePreprocessor

class TestHarshConditionsPreprocessing(unittest.TestCase):
    """실환경 악조건(저조도, 역광, 저해상도) 보정 엔진의 수치적 복원력을 검증합니다."""

    def setUp(self):
        self.preprocessor = ImagePreprocessor()

    def test_low_light_gamma_enhancement(self):
        """극도로 어두운 저조도 가상 이미지에 대해 감마 보정이 자연스럽게 밝기를 상향시키는지 검증합니다."""
        # 1. 평균 픽셀 밝기 약 30 수준의 어두운 BGR 프레임 생성 (240x320)
        low_light_frame = np.ones((240, 320, 3), dtype=np.uint8) * 30
        
        # 2. 야간 보정 적용 (is_night=True)
        enhanced_frame = self.preprocessor.process(low_light_frame, is_night=True)
        
        # 3. 평균 밝기 비교 검증
        avg_before = np.mean(low_light_frame)
        avg_after = np.mean(enhanced_frame)
        
        # 감마 1.6 보정에 의해 밝기가 유의미하게 상승했어야 함
        self.assertGreater(avg_after, avg_before)
        # 원본(30) 대비 감마 보정으로 밝기가 충분히 상승했는지 확인 (최소 60 이상)
        self.assertGreater(avg_after, 60.0)

    def test_backlight_contrast_recovery(self):
        """피사체가 까맣게 타버리는 극단적 역광 조건에서 CLAHE 필터가 윤곽 국부 대비를 복구하는지 검증합니다."""
        # 1. 왼쪽은 어둡고(10) 오른쪽은 매우 밝은(240) 역광 시뮬레이션 프레임 생성
        backlit_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        backlit_frame[:, :160] = 10
        backlit_frame[:, 160:] = 240
        
        # 2. 역광 보정 적용 (is_backlit=True)
        restored_frame = self.preprocessor.process(backlit_frame, is_backlit=True)
        
        # 3. 어두웠던 좌측 영역(인물이 존재할 실루엣 공간)의 밝기 균일화도(CLAHE 적용 여부) 측정
        left_before = np.mean(backlit_frame[:, :160])
        left_after = np.mean(restored_frame[:, :160])
        
        # 역광 보정 활성화 시, 어두웠던 인물 음영 영역의 픽셀 조도가 상승하여 보정되었는지 확인
        self.assertGreater(left_after, left_before)
        self.assertGreater(left_after, 20.0)

    def test_low_res_roi_sharpening(self):
        """저해상도 CCTV 픽셀 뭉개짐 상황에서 적응형 선명도 강화(Sharpening) 필터가 에지 선명도를 복원하는지 검증합니다."""
        # 1. 텍스처를 가진 가상 원본 이미지 및 이를 심하게 블러 처리한 저해상도 모사 ROI 생성
        np.random.seed(42)
        base_roi = (np.random.rand(128, 64, 3) * 255).astype(np.uint8)
        low_res_roi = cv2.GaussianBlur(base_roi, (7, 7), 0)
        
        # 2. 선명도 복원 필터 적용
        sharpened_roi = self.preprocessor.enhance_roi(low_res_roi)
        
        # 3. Laplacian Variance를 사용한 엣지/선명도 수치(Sharpness Score) 측정
        def get_sharpness_score(img):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gray, cv2.CV_64F).var()
            
        score_before = get_sharpness_score(low_res_roi)
        score_after = get_sharpness_score(sharpened_roi)
        
        # 언샤프 마스킹 선명화 필터 적용 후 선명도 점수가 뚜렷하게 상승했는지 검증
        self.assertGreater(score_after, score_before)
        # 선명화 효과가 눈에 띄게 적용되었는지 확인 (최소 1.25배 이상 개선)
        self.assertGreater(score_after, score_before * 1.25)

if __name__ == "__main__":
    unittest.main()
