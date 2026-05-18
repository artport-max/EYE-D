"""
visual_demo.py
--------------
실시간 카메라/동영상 파일 입력을 받아 악조건(저조도 야간, 역광, 저해상도) 필터 효과를
사이드-바이-사이드(Side-by-Side)로 모니터링하고 키보드로 실시간 토글 제어해 볼 수 있는 
인터랙티브 비주얼 통합 데모 테스터입니다.

실행 방법:
    $ python tools/visual_demo.py --video <영상경로>
    (영상경로가 없으면 자동으로 조도가 순환 변동되는 가상 시뮬레이션 비디오가 자율 생성되어 구동됩니다!)

단축키 안내:
    - 'N' 키: 야간/저조도 감마 보정 필터 On/Off 토글
    - 'B' 키: 역광 국부 대비 보정 필터(CLAHE) On/Off 토글
    - 'S' 키: 저해상도 인물 ROI 선명화 필터(Sharpening) On/Off 토글
    - 'Q' 키 또는 ESC 키: 데모 안전 정지 및 종료
"""

import cv2
import numpy as np
import time
import argparse
import sys
import os

# 모듈 상대 경로 임포트 보정 (tools/visual_demo.py 상위인 edge/ 디렉토리를 루트로 확보)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.preprocessor import ImagePreprocessor

def make_synthetic_frame(frame_idx):
    """실제 비디오 파일이 없을 때, 조도가 어두워졌다가 빛번짐이 발생하는 가상 시뮬레이션 프레임을 실시간 합성합니다."""
    # 360x640 크기의 프레임 생성
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    
    # 1. 가상 실내 텍스처 배경 합성 (체크무늬 및 바닥선)
    for i in range(12):
        cv2.line(frame, (i * 60, 0), (i * 60, 360), (40, 40, 40), 1)
        cv2.line(frame, (0, i * 40), (640, i * 40), (40, 40, 40), 1)
        
    # 가상 보행자 궤적 원형 시뮬레이션
    angle = (frame_idx * 0.03) % (2 * np.pi)
    px = int(320 + 200 * np.cos(angle))
    py = int(180 + 100 * np.sin(angle))
    
    # 가상 보행자 Bounding Box 그리기
    cv2.rectangle(frame, (px - 20, py - 40), (px + 20, py + 40), (0, 255, 0), 2)
    cv2.putText(frame, "PERSON #1", (px - 25, py - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
    # 옷 텍스처 시뮬레이션
    cv2.rectangle(frame, (px - 15, py - 35), (px + 15, py + 35), (100, 100, 200), -1)
    
    # 2. 동적 조도 연출 (프레임 인덱스에 따라 어두워졌다가 역광 상태로 전환)
    cycle = frame_idx % 300
    if cycle < 100:
        # 정상 조도
        pass
    elif cycle < 200:
        # 야간 저조도 상황 모사 (조도가 어두운 20~30 수준으로 강하)
        darkness = 1.0 - ((cycle - 100) / 100.0) * 0.8  # 밝기 최대 80% 감쇠
        frame = (frame * darkness).astype(np.uint8)
    else:
        # 역광 상황 모사 (왼쪽 구석에 극단적 강한 광원 255 추가, 우측은 매우 어둡게 그늘)
        light_pos = (50, 50)
        for r in range(150, 0, -10):
            color = int(255 * (1.0 - r/150.0))
            cv2.circle(frame, light_pos, r, (color, color, color), -1)
        
        # 우측 그늘 부분 어둡게 깎기
        frame[:, 300:] = (frame[:, 300:] * 0.25).astype(np.uint8)
        
    return frame

def run_visual_demo(video_path=None):
    # 전처리 필터 초기화
    preprocessor = ImagePreprocessor()
    
    cap = None
    if video_path and os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        print(f"[✔] 실제 동영상 파일 로드 완료: {video_path}")
    else:
        print("[!] 입력 비디오가 없거나 경로가 잘못되어 가상 악조건 시뮬레이션 모드로 데모를 가동합니다.")
        
    # 실시간 모드 상태 플래그
    mode_night = False
    mode_backlight = False
    mode_sharpen = True  # ROI 선명화 디폴트 활성화
    
    frame_idx = 0
    
    print("\n" + "="*60)
    print(" ■ EYE-D Edge 실환경 극복 비주얼 인터랙티브 데모 가동 ■")
    print("="*60)
    print(" [단축키 컨트롤 보드]")
    print("   - N 키 누름: 야간/저조도 감마 보정 On / Off")
    print("   - B 키 누름: 역광 CLAHE 강도 보정 On / Off")
    print("   - S 키 누름: 저해상도 인물 ROI Sharpening On / Off")
    print("   - Q 또는 ESC 키: 데모 윈도우 끄기 및 종료")
    print("="*60 + "\n")
    
    cv2.namedWindow("EYE-D Edge Visual Demo Center", cv2.WINDOW_AUTOSIZE)
    
    try:
        while True:
            # 1. 프레임 소스 획득 (가상 시뮬레이션 또는 비디오 파일)
            if cap is not None:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # 동영상 무한 반복 재생
                    continue
            else:
                frame = make_synthetic_frame(frame_idx)
                
            frame_idx += 1
            
            # 원본 보존용 복제
            original_frame = frame.copy()
            
            # 2. 보정 엔진 적용
            processed_frame = preprocessor.process(
                original_frame, 
                is_night=mode_night, 
                is_backlit=mode_backlight
            )
            
            # 3. ROI 인물 선명화 모사 테스트 (화면 내 가상 BBox가 있을 경우)
            roi_y1, roi_y2, roi_x1, roi_x2 = 120, 240, 290, 350
            roi_original = original_frame[roi_y1:roi_y2, roi_x1:roi_x2].copy()
            
            if mode_sharpen:
                roi_processed = preprocessor.enhance_roi(roi_original)
            else:
                roi_processed = roi_original.copy()
            
            # 4. 실시간 상태 텍스트 HUD 오버레이 합성 (사이드 바이 사이드 화면)
            h, w, c = original_frame.shape
            canvas = np.zeros((h + 60, w * 2, c), dtype=np.uint8)
            
            # 좌측: 원본 뷰어 
            canvas[40:40+h, :w] = original_frame
            # 우측: 전처리 튜닝 보정 뷰어
            canvas[40:40+h, w:] = processed_frame
            
            # 헤더 텍스트 장식
            cv2.putText(canvas, "CAMERA STREAM: ORIGINAL RAW VIEW", (15, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(canvas, "EYE-D TUNED: ACTIVE REAL-TIME ENHANCED VIEW", (w + 15, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # 5. 상태 컨트롤 HUD 패널 그리기 (하단 여백 바)
            hud_y = h + 42
            color_n = (0, 255, 0) if mode_night else (0, 0, 255)
            color_b = (0, 255, 0) if mode_backlight else (0, 0, 255)
            color_s = (0, 255, 0) if mode_sharpen else (0, 0, 255)
            
            status_n = "ACTIVE (GAMMA 1.6)" if mode_night else "DISABLED"
            status_b = "ACTIVE (CLAHE 4.0)" if mode_backlight else "DISABLED"
            status_s = "ACTIVE (UNSHARP)" if mode_sharpen else "DISABLED"
            
            cv2.putText(canvas, f"[N] NIGHT MODE: {status_n}", (15, hud_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_n, 2)
            cv2.putText(canvas, f"[B] BACKLIGHT MODE: {status_b}", (w // 2 - 80, hud_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_b, 2)
            cv2.putText(canvas, f"[S] ROI SHARPEN FILTER: {status_s}", (w + 15, hud_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_s, 2)
            cv2.putText(canvas, "PRESS 'Q' TO QUIT DEMO", (w * 2 - 220, hud_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # 6. 우측 하단에 저해상도 인물 ROI 실시간 선명화 돋보기 창 합성
            mag_h, mag_w = 120, 100
            mag_y = h - mag_h - 10
            mag_x = w * 2 - mag_w - 20
            
            # 돋보기 바깥 테두리 그리기
            cv2.rectangle(canvas, (mag_x - 2, mag_y - 22), (mag_x + mag_w + 2, mag_y + mag_h + 2), (255, 255, 0), 2)
            cv2.rectangle(canvas, (mag_x - 2, mag_y - 22), (mag_x + mag_w + 2, mag_y), (255, 255, 0), -1)
            cv2.putText(canvas, "ROI ZOOM", (mag_x + 10, mag_y - 6), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
            
            # 크롭된 ROI 이미지를 돋보기 창 크기에 맞추어 확대
            resized_roi = cv2.resize(roi_processed, (mag_w, mag_h))
            canvas[mag_y:mag_y+mag_h, mag_x:mag_x+mag_w] = resized_roi
            
            # 7. 모니터 출력 및 키보드 입력 핸들러
            cv2.imshow("EYE-D Edge Visual Demo Center", canvas)
            
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord('q') or key == 27:  # Q 키 또는 ESC
                print("[✔] 사용자에 의해 데모가 안전하게 중단되었습니다.")
                break
            elif key == ord('n'):  # N 키
                mode_night = not mode_night
                print(f"[!] 야간 감마 보정 모드 변경 ➔ {mode_night}")
            elif key == ord('b'):  # B 키
                mode_backlight = not mode_backlight
                print(f"[!] 역광 대비 보정 모드 변경 ➔ {mode_backlight}")
            elif key == ord('s'):  # S 키
                mode_sharpen = not mode_sharpen
                print(f"[!] 인물 ROI 선명도 필터 변경 ➔ {mode_sharpen}")
                
            time.sleep(0.01)
            
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        print("[✔] 비주얼 데모 리소스가 안전하게 해제되었습니다. 데모 센터 종료.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EYE-D Real-time Visual Demonstration Tool")
    parser.add_argument("--video", type=str, default=None, help="테스트할 동영상 파일 (.mp4 등) 경로")
    args = parser.parse_args()
    
    run_visual_demo(args.video)
