#!/bin/bash

# ==============================================================================
# 다채널 RTSP 스트림 모니터링 스크립트 (view_streams.sh)
#
# 사용법:
#   ./view_streams.sh [전송노드_IP]
#   (IP를 입력하지 않으면 기본값은 localhost)
#
# 종료 방법:
#   pkill ffplay 또는 개별 창 닫기
# ==============================================================================

# 전송노드 IP 설정 (기본값: localhost)
IP_ADDR="${1:-localhost}"
RTSP_SERVER="rtsp://$IP_ADDR:8554"

echo "========================================================"
echo "    다채널 RTSP 스트림 모니터링 시작 (ffplay)"
echo "    대상 서버: $RTSP_SERVER"
echo "========================================================"

# ffplay 설치 여부 확인
if ! command -v ffplay &> /dev/null; then
    echo "[ERROR] ffplay가 설치되어 있지 않거나 PATH에 존재하지 않습니다."
    echo "Ubuntu 기준 설치법: sudo apt install ffmpeg"
    exit 1
fi

# cam01, cam02, cam03 개별 창을 백그라운드에서 실행
echo "[CAM 01] 재생 시도..."
ffplay -loglevel error -window_title "CAM 01 - $RTSP_SERVER/cam01" "$RTSP_SERVER/cam01" > /dev/null 2>&1 &

echo "[CAM 02] 재생 시도..."
ffplay -loglevel error -window_title "CAM 02 - $RTSP_SERVER/cam02" "$RTSP_SERVER/cam02" > /dev/null 2>&1 &

echo "[CAM 03] 재생 시도..."
ffplay -loglevel error -window_title "CAM 03 - $RTSP_SERVER/cam03" "$RTSP_SERVER/cam03" > /dev/null 2>&1 &

echo "--------------------------------------------------------"
echo "모든 모니터링 창이 개별 백그라운드 스레드로 실행되었습니다."
echo "창을 모두 일괄 종료하려면 다음 명령을 실행하십시오:"
echo "  pkill ffplay"
echo "========================================================"
