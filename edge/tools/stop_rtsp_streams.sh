#!/bin/bash

# ==============================================================================
# 다채널 RTSP 스트림 송출 중단 스크립트 (stop_rtsp_streams.sh)
#
# 역할:
#   1. 백그라운드에서 동작 중인 FFmpeg 프로세스를 종료합니다.
#   2. Docker로 구동 중인 Mediamtx RTSP 미디어 서버 컨테이너를 중지합니다.
# ==============================================================================

CONTAINER_NAME="mediamtx"

echo "========================================================"
echo "    다채널 RTSP 스트림 송출 및 서버를 중단합니다..."
echo "========================================================"

# 1. FFmpeg 프로세스 종료
if pgrep ffmpeg > /dev/null; then
    pkill ffmpeg
    echo "[SUCCESS] 모든 FFmpeg 스트리밍 프로세스가 중단되었습니다."
else
    echo "[INFO] 실행 중인 FFmpeg 프로세스가 없습니다."
fi

# 2. Docker Mediamtx 컨테이너 중지
if command -v docker &> /dev/null; then
    if docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" | grep -q "${CONTAINER_NAME}"; then
        echo "구동 중인 ${CONTAINER_NAME} Docker 컨테이너를 중지합니다..."
        docker stop ${CONTAINER_NAME} > /dev/null 2>&1
        echo "[SUCCESS] Mediamtx 서버 컨테이너가 안전하게 종료되었습니다."
    else
        echo "[INFO] 실행 중인 Mediamtx 컨테이너가 없습니다."
    fi
fi

echo "========================================================"
