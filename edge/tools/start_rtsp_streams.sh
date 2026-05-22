#!/bin/bash

# ==============================================================================
# 다채널 RTSP 스트림 송출 스크립트 (start_rtsp_streams.sh)
#
# 역할: data 디렉토리 내의 3개 비디오 파일을 FFmpeg을 사용하여
#       각각 cam01, cam02, cam03 경로로 무한 루프 스트리밍합니다.
#
# 중지 방법: pkill ffmpeg 또는 ./stop_rtsp_streams.sh 실행
# ==============================================================================

# 스크립트의 현재 디렉토리 기준 프로젝트 루트 및 데이터 디렉토리 계산
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
RTSP_SERVER="rtsp://localhost:8554"

# 송출할 파일 정의
FILE1="$DATA_DIR/16300000.avi"
FILE2="$DATA_DIR/16300002.avi"
FILE3="$DATA_DIR/16300003.avi"

echo "========================================================"
echo "    다채널 RTSP 스트림 무한 루프 송출을 시작합니다"
echo "========================================================"

# cam01 송출 (16300000.avi)
if [ -f "$FILE1" ]; then
    echo "[CAM 1] 송출 중: $FILE1 -> $RTSP_SERVER/cam01"
    ffmpeg -re -stream_loop -1 -i "$FILE1" -c:v libx264 -preset ultrafast -an -f rtsp "$RTSP_SERVER/cam01" > /dev/null 2>&1 &
else
    echo "[ERROR] 파일을 찾을 수 없습니다: $FILE1"
fi

# cam02 송출 (16300002.avi)
if [ -f "$FILE2" ]; then
    echo "[CAM 2] 송출 중: $FILE2 -> $RTSP_SERVER/cam02"
    ffmpeg -re -stream_loop -1 -i "$FILE2" -c:v libx264 -preset ultrafast -an -f rtsp "$RTSP_SERVER/cam02" > /dev/null 2>&1 &
else
    echo "[ERROR] 파일을 찾을 수 없습니다: $FILE2"
fi

# cam03 송출 (g1.mp4)
if [ -f "$FILE3" ]; then
    echo "[CAM 3] 송출 중: $FILE3 -> $RTSP_SERVER/cam03"
    ffmpeg -re -stream_loop -1 -i "$FILE3" -c:v libx264 -preset ultrafast -an -f rtsp "$RTSP_SERVER/cam03" > /dev/null 2>&1 &
else
    echo "[ERROR] 파일을 찾을 수 없습니다: $FILE3"
fi

echo "--------------------------------------------------------"
echo "모든 스트림 송출이 백그라운드에서 실행되었습니다."
echo "스트림 송출을 중단하려면 다음 명령어를 실행하십시오:"
echo "  pkill ffmpeg"
echo "========================================================"
