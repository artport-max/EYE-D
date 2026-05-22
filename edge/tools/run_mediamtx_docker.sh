#!/bin/bash

# ==============================================================================
# Mediamtx RTSP 미디어 서버 Docker 구동 스크립트 (run_mediamtx_docker.sh)
#
# 사용법:
#   - 구동: ./run_mediamtx_docker.sh
#   - 중지: ./run_mediamtx_docker.sh stop
# ==============================================================================

CONTAINER_NAME="mediamtx"

# Docker 설치 및 권한 확인
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker가 설치되어 있지 않거나 PATH에 존재하지 않습니다."
    exit 1
fi

# 1. 중지 명령어 처리
if [ "$1" == "stop" ]; then
    echo "========================================================"
    echo "    RTSP 미디어 서버 (Mediamtx) 컨테이너를 중지합니다..."
    echo "========================================================"
    
    if docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" | grep -q "${CONTAINER_NAME}"; then
        docker stop ${CONTAINER_NAME} > /dev/null 2>&1
        echo "[SUCCESS] Mediamtx 컨테이너가 정상적으로 종료되었습니다."
    else
        echo "[INFO] 구동 중인 Mediamtx 컨테이너가 없습니다."
    fi
    echo "========================================================"
    exit 0
fi

# 2. 구동 프로세스
echo "========================================================"
echo "    RTSP 미디어 서버 (Mediamtx) 상태 점검 및 구동"
echo "========================================================"

# 이미 구동 중인지 확인
if docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" | grep -q "${CONTAINER_NAME}"; then
    echo "[INFO] Mediamtx 컨테이너가 이미 백그라운드에서 구동 중입니다."
    echo "RTSP 서버 주소: rtsp://localhost:8554"
    echo "========================================================"
    exit 0
fi

# 중지 상태인 동일 이름의 컨테이너 정리
if docker ps -a --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "기존에 존재하던 중지 상태의 ${CONTAINER_NAME} 컨테이너를 정리합니다..."
    docker rm -f ${CONTAINER_NAME} > /dev/null 2>&1
fi

# Mediamtx 컨테이너 백그라운드 구동
echo "Mediamtx 컨테이너(bluenviron/mediamtx:latest)를 백그라운드에서 시작합니다..."
docker run -d --rm --name ${CONTAINER_NAME} --network=host bluenviron/mediamtx:latest

# 기동 대기
echo "네트워크 바인딩 및 서버 기동 대기 중 (2초)..."
sleep 2

# 최종 구동 상태 확인
if docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" | grep -q "${CONTAINER_NAME}"; then
    echo "[SUCCESS] Mediamtx 컨테이너가 백그라운드에서 성공적으로 구동되었습니다."
    echo "RTSP 서버 기본 포트: 8554 (TCP/UDP)"
    echo "RTSP 기본 송출 주소 예시: rtsp://localhost:8554/cam01"
else
    echo "[ERROR] Mediamtx 컨테이너 구동에 실패했습니다. 'docker logs ${CONTAINER_NAME}' 명령으로 원인을 확인하십시오."
fi
echo "========================================================"
