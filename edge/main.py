import time
import cv2
import argparse
import logging
import sys
import signal
import os

# headless 환경 대비 cv2 highgui 함수 모킹 패치
def _mock_imshow(*args, **kwargs):
    pass
_mock_imshow._is_mock = True

if not hasattr(cv2, 'imshow'):
    cv2.imshow = _mock_imshow
if not hasattr(cv2, 'destroyAllWindows'):
    cv2.destroyAllWindows = lambda *args, **kwargs: None
if not hasattr(cv2, 'destroyWindow'):
    cv2.destroyWindow = lambda *args, **kwargs: None
if not hasattr(cv2, 'namedWindow'):
    cv2.namedWindow = lambda *args, **kwargs: None
if not hasattr(cv2, 'waitKey'):
    cv2.waitKey = lambda *args, **kwargs: 1

# edge 디렉토리 내부의 소스 모듈(src.*)을 올바르게 찾을 수 있도록 현재 디렉토리를 path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from src.core.pipeline_runner import PipelineRunner
from src.core.analytics_engine import AnalyticsEngine
from src.infrastructure.db_client import DBTester
from src.infrastructure.monitoring_agent import MonitoringAgent
from src.infrastructure.http_client import ResilientServerSender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

# 전역 변수로 선언하여 시그널 핸들러에서 접근 가능하도록 함
running = True

def signal_handler(sig, frame):
    global running
    logger.info("종료 시그널 수신. 파이프라인을 안전하게 종료합니다...")
    running = False

def main():
    parser = argparse.ArgumentParser(description="Jetson Orin Nano Edge AI Pipeline (Production)")
    parser.add_argument("--source", type=str, default="0", help="RTSP URL, 비디오 파일 경로 또는 웹캠 ID (기본값: 0)")
    parser.add_argument("--camera-id", type=str, default="CAM_01", help="카메라 식별자")
    parser.add_argument("--db-host", type=str, default="localhost", help="Qdrant DB 호스트")
    parser.add_argument("--db-port", type=int, default=6333, help="Qdrant DB 포트")
    parser.add_argument("--tensorrt", action="store_true", help="TensorRT 엔진 사용 여부")
    parser.add_argument("--no-onnx", action="store_false", dest="onnx", help="Re-ID ONNX Runtime 가속 비활성화")
    parser.add_argument("--display", action="store_true", help="화면 출력 여부 (UI가 있는 환경에서만 사용)")
    parser.add_argument("--server-url", type=str, default="http://localhost:8000", help="FastAPI 백엔드 서버 URL")
    parser.add_argument("--dry-run", action="store_true", help="Re-ID 벡터 생성까지만 수행하고 DB 저장 및 외부 서버 전송을 생략 (검증용)")
    args = parser.parse_args()

    # 종료 시그널 등록 (Ctrl+C 등)
    signal.signal(signal.SIGINT, signal_handler)

    # 1. 인프라 연결 (DB 및 모니터링)
    db_client = None
    if not args.dry_run:
        logger.info(f"DB 연결 시도: {args.db_host}:{args.db_port}")
        db_client = DBTester()
        try:
            db_client.connect(host=args.db_host, port=args.db_port)
            logger.info("Qdrant DB 연결 성공")
        except Exception as e:
            logger.warning(f"DB 연결 실패 (로컬 모드로 진행할 수 있습니다): {e}")
            db_client = None
    else:
        logger.info("Dry-run 모드 활성화: Qdrant DB 연결을 생략합니다.")

    monitor = MonitoringAgent()
    
    # 2. 파이프라인 및 분석 엔진 초기화
    collection_name = 'prod_reid_collection'
    config = {
        'use_tensorrt': args.tensorrt,
        'use_onnx': args.onnx,
        'collection_name': collection_name,
        'send_interval_frames': 10,
        'dry_run': args.dry_run
    }
    
    # 백엔드 서버 전송용 HTTP 클라이언트 초기화 (복원력 탑재)
    http_sender = None
    if not args.dry_run:
        logger.info(f"서버 전송 클라이언트 초기화: {args.server_url}")
        http_sender = ResilientServerSender(base_url=args.server_url, db_path="edge_resilience_buffer.db")
    else:
        logger.info("Dry-run 모드 활성화: 서버 전송 클라이언트 초기화를 생략합니다.")
    
    runner = PipelineRunner(config=config, db_client=db_client, http_sender=http_sender)
    analytics = AnalyticsEngine(db_client=db_client, collection_name=collection_name)
    
    logger.info("AI 파이프라인 초기화 중...")
    runner.start()

    # 3. 비디오 캡처 초기화
    # HighGUI(화면 표시) 기능 미지원 시 display 옵션 자동 끄기
    if args.display and getattr(cv2.imshow, '_is_mock', False):
        logger.warning("현재 OpenCV 빌드 환경에 HighGUI(디스플레이 화면 출력) 기능이 포함되어 있지 않습니다. --display 플래그를 자동으로 비활성화합니다.")
        args.display = False

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error(f"비디오 소스를 열 수 없습니다: {args.source}")
        sys.exit(1)

    logger.info(f"스트림 처리 시작: {args.source} (카메라 ID: {args.camera_id})")
    fps_counter = 0
    start_time = time.time()
    last_monitor_time = time.time()

    global running
    while running and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logger.info("비디오 스트림이 종료되었거나 신호가 끊겼습니다.")
            break
            
        # 프레임 처리 (추론 및 Re-ID 추출)
        result = runner.process_frame(frame, camera_id=args.camera_id)
        
        # 분석 엔진 업데이트 (출입 카운트, 체류 시간 계산)
        if not args.dry_run and result and result.get('tracks'):
            analytics.update_tracks(result['tracks'], camera_id=args.camera_id)
        
        # 주기적 상태 모니터링 (5초마다 로그 출력)
        current_time = time.time()
        if current_time - last_monitor_time >= 5.0:
            sys_stats = monitor.sample()
            anl_stats = analytics.get_statistics()
            logger.info(f"시스템 상태: CPU {sys_stats.get('cpu_percent')}% | Mem {sys_stats.get('memory_percent')}%")
            logger.info(f"분석 통계: 입장 {anl_stats.get('entrance_count')}명 | 퇴장 {anl_stats.get('exit_count')}명 | 현재 추적 {anl_stats.get('total_tracked')}명")
            last_monitor_time = current_time

        # 시각화 (옵션)
        if args.display and result and result.get('tracks'):
            for track in result['tracks']:
                x1, y1, x2, y2 = track['bbox']
                tid = track['track_id']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"ID: {tid}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imshow("Production Stream", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.info("'q' 키가 입력되어 종료합니다.")
                break

        fps_counter += 1

    # 4. 종료 처리
    elapsed_time = time.time() - start_time
    # 0 나누기 에러 방지
    elapsed_time = elapsed_time if elapsed_time > 0 else 0.001 
    logger.info(f"프로세스 종료. 총 처리 시간: {elapsed_time:.2f}초, 평균 처리 속도: {fps_counter/elapsed_time:.2f} FPS")
    
    cap.release()
    if args.display:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
    runner.stop()
    
    # 백그라운드 전송 스레드 종료 및 정리
    if http_sender:
        http_sender.stop()

if __name__ == "__main__":
    main()
