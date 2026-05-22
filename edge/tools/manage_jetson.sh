#!/bin/bash

# ==============================================================================
# EYE-D Jetson Edge 서비스 통합 관리 스크립트 (manage_jetson.sh)
#
# 역할: Jetson 환경에서 Docker 기반 Qdrant DB 및 엣지 AI 파이프라인 컨테이너의
#       빌드, 구동(start), 중지(stop), 모니터링(logs, status), 초기화(cleanup)를
#       통합적으로 관리합니다.
# ==============================================================================

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$EDGE_DIR/.." && pwd)"

# 컨테이너 이름 정의
EDGE_CONTAINER="eyed-edge-service"
QDRANT_CONTAINER="qdrant"
EDGE_IMAGE="eyed-edge:latest"

# 기본 설정값
SOURCE="rtsp://192.168.45.7:8554/cam01"
CAMERA_ID="CAM_01"
SERVER_URL="http://192.168.45.176:8000"
DISPLAY_ON=false
DRY_RUN=false
FOLLOW_LOGS=false
LOG_SERVICE="edge"

# 도움말 출력 함수
show_help() {
    echo -e "${BLUE}EYE-D Jetson Edge 서비스 관리 도구${NC}"
    echo "사용법: $0 [Command] [Options]"
    echo ""
    echo "명령어(Command):"
    echo "  start       Qdrant DB 및 엣지 AI 파이프라인 컨테이너를 구동합니다."
    echo "  stop        구동 중인 엣지 서비스 및 Qdrant 컨테이너를 중지하고 제거합니다."
    echo "  restart     서비스를 재시작합니다 (stop 후 start)."
    echo "  status      컨테이너의 현재 구동 상태 및 포트 매핑 정보를 확인합니다."
    echo "  logs        컨테이너 로그를 출력합니다. (기본값: edge)"
    echo "  build       Dockerfile.edge를 사용하여 엣지 서비스 도커 이미지를 빌드합니다."
    echo "  cleanup     컨테이너를 중지하고 로컬 DB/전송 버퍼 캐시를 완전히 삭제하여 초기화합니다."
    echo ""
    echo "옵션(Options) [start / restart 시 사용 가능]:"
    echo "  -s, --source <source>      비디오 소스 입력 (RTSP URL, 비디오 파일 경로, 웹캠 인덱스) (기본값: $SOURCE)"
    echo "  -c, --camera-id <id>       카메라 고유 식별자 (기본값: $CAMERA_ID)"
    echo "  -u, --server-url <url>     중앙 백엔드 FastAPI 서버 URL (기본값: $SERVER_URL)"
    echo "  -d, --display              GUI 화면 출력을 활성화합니다. (X11 디스플레이 포워딩 설정 적용)"
    echo "  --dry-run                  드라이런 모드로 실행합니다. (DB 저장 및 백엔드 전송 생략)"
    echo ""
    echo "옵션(Options) [logs 시 사용 가능]:"
    echo "  -f, --follow               실시간 로그 흐름(tail -f)을 모니터링합니다."
    echo "  --service <edge|qdrant>    로그를 확인할 서비스를 선택합니다. (기본값: edge)"
    echo ""
    echo "예시(Examples):"
    echo "  * 기본 시작:          $0 start"
    echo "  * RTSP 소스 지정 시작:  $0 start -s rtsp://192.168.45.7:8554/cam01 -c CAM_01"
    echo "  * 화면 표시하며 시작:  $0 start -d"
    echo "  * 로그 실시간 모니터링: $0 logs -f"
    echo "  * 데이터 완전 초기화:   $0 cleanup"
}

# Docker 실행 환경 및 권한 체크
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}[ERROR] Docker가 설치되어 있지 않거나 PATH에 존재하지 않습니다.${NC}"
        exit 1
    fi

    if ! docker ps &> /dev/null; then
        echo -e "${RED}[ERROR] Docker 데몬이 실행 중이 아니거나 권한이 없습니다.${NC}"
        echo -e "${YELLOW}[TIP] 'sudo systemctl start docker' 또는 현재 사용자를 docker 그룹에 추가하십시오: 'sudo usermod -aG docker \$USER'${NC}"
        exit 1
    fi
}

# NVIDIA Container Runtime 체크 (Jetson 필수)
check_nvidia_runtime() {
    if ! docker info | grep -q "Runtimes:.*nvidia"; then
        echo -e "${YELLOW}[WARNING] Docker 환경에 nvidia 런타임이 감지되지 않았습니다.${NC}"
        echo -e "${YELLOW}Jetson GPU 가속 구동을 위해선 'nvidia-container-toolkit'이 올바르게 설치되어 있어야 합니다.${NC}"
        echo -e "설치 명령어 예시:"
        echo -e "  sudo apt-get install -y nvidia-docker2"
        echo -e "  sudo systemctl restart docker"
        echo ""
        read -p "NVIDIA 런타임 없이 CPU 모드로 계속 구동하시겠습니까? (y/N): " choice
        case "$choice" in 
            y|Y ) echo -e "${YELLOW}NVIDIA 런타임 없이 계속 진행합니다.${NC}";;
            * ) echo -e "${RED}중단되었습니다.${NC}"; exit 1;;
        esac
        return 1
    fi
    return 0
}

# Docker 이미지 존재 여부 확인 및 빌드 유도
ensure_image_exists() {
    if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${EDGE_IMAGE}$"; then
        echo -e "${YELLOW}[INFO] 엣지 서비스 도커 이미지(${EDGE_IMAGE})가 로컬에 존재하지 않습니다.${NC}"
        echo -e "이미지 빌드를 먼저 시도합니다..."
        build_image
    fi
}

# 도커 이미지 빌드
build_image() {
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D 엣지 서비스 도커 이미지 빌드 시작${NC}"
    echo "========================================================"
    cd "$EDGE_DIR"
    docker build -t "$EDGE_IMAGE" -f Dockerfile.edge .
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS] 엣지 이미지 빌드 성공 ($EDGE_IMAGE)${NC}"
    else
        echo -e "${RED}[ERROR] 이미지 빌드 실패! Dockerfile.edge 설정을 확인하십시오.${NC}"
        exit 1
    fi
    echo "========================================================"
}

# 서비스 시작
start_services() {
    check_docker
    ensure_image_exists

    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Jetson Edge AI 서비스 구동 시작${NC}"
    echo "========================================================"

    # 1. Qdrant DB 컨테이너 구동 여부 확인 및 기동
    if docker ps --filter "name=^/${QDRANT_CONTAINER}$" --filter "status=running" | grep -q "${QDRANT_CONTAINER}"; then
        echo -e "${GREEN}[INFO] Qdrant DB 컨테이너가 이미 구동 중입니다.${NC}"
    else
        # 중지 상태인 동일 이름의 컨테이너 정리
        if docker ps -a --filter "name=^/${QDRANT_CONTAINER}$" | grep -q "${QDRANT_CONTAINER}"; then
            docker rm -f "$QDRANT_CONTAINER" > /dev/null 2>&1
        fi
        
        echo -e "${YELLOW}[Qdrant] DB 컨테이너를 구동합니다...${NC}"
        # 로컬 보존용 qdrant_storage 디렉토리 생성
        mkdir -p "$EDGE_DIR/qdrant_storage"
        
        docker run -d \
            --name "$QDRANT_CONTAINER" \
            --restart unless-stopped \
            -p 6333:6333 \
            -p 6334:6334 \
            -v "$EDGE_DIR/qdrant_storage:/qdrant/storage:z" \
            qdrant/qdrant > /dev/null
            
        sleep 2
        if docker ps --filter "name=^/${QDRANT_CONTAINER}$" --filter "status=running" | grep -q "${QDRANT_CONTAINER}"; then
            echo -e "${GREEN}[SUCCESS] Qdrant DB 기동 완료 (Dashboard: http://localhost:6333/dashboard)${NC}"
        else
            echo -e "${RED}[ERROR] Qdrant DB 컨테이너 실행에 실패했습니다.${NC}"
        fi
    fi

    # 2. 기존 에지 서비스 컨테이너 정리
    if docker ps -a --filter "name=^/${EDGE_CONTAINER}$" | grep -q "${EDGE_CONTAINER}"; then
        echo -e "${YELLOW}기존에 구동 또는 정지되어 있던 ${EDGE_CONTAINER} 컨테이너를 중지 및 제거합니다...${NC}"
        docker rm -f "$EDGE_CONTAINER" > /dev/null 2>&1
    fi

    # 3. NVIDIA 런타임 체크 및 가속 옵션 설정
    local runtime_flag=""
    if check_nvidia_runtime; then
        runtime_flag="--runtime nvidia"
    fi

    # 4. GUI 화면(Display) 활성화 환경 설정
    local display_flag=""
    if [ "$DISPLAY_ON" = true ]; then
        echo -e "${YELLOW}[DISPLAY] GUI 디스플레이 투사 권한 설정 및 볼륨 바인딩을 추가합니다.${NC}"
        
        # 호스트 GUI 서버에 도커 로컬 컨테이너 접근 권한 부여
        if command -v xhost &> /dev/null; then
            xhost +local:docker > /dev/null 2>&1
        else
            echo -e "${RED}[WARNING] xhost 명령어가 존재하지 않아 디스플레이 포워딩이 제한될 수 있습니다.${NC}"
        fi

        # DISPLAY 환경변수 매핑 및 X11 소켓 바인딩 설정 추가
        display_flag="-e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:ro"
    fi

    # 5. 파이프라인 구동 옵션 구성
    local run_args=("python" "main.py" "--source" "$SOURCE" "--camera-id" "$CAMERA_ID" "--server-url" "$SERVER_URL")
    
    # Jetson 환경에서 실행되므로 기본적으로 GPU TensorRT 가속 활성화
    run_args+=("--tensorrt")

    if [ "$DRY_RUN" = true ]; then
        run_args+=("--dry-run")
        echo -e "${YELLOW}[DRY-RUN] 드라이런 모드가 활성화되어 DB 저장 및 서버 전송이 스킵됩니다.${NC}"
    fi

    if [ "$DISPLAY_ON" = true ]; then
        run_args+=("--display")
    fi

    # 6. 에지 컨테이너 백그라운드 시작
    echo -e "${YELLOW}[Edge] AI 파이프라인 컨테이너를 시작합니다...${NC}"
    echo -e "   - 소스: $SOURCE"
    echo -e "   - 카메라 ID: $CAMERA_ID"
    echo -e "   - 백엔드 URL: $SERVER_URL"
    
    # Docker 실행
    docker run -d \
        --name "$EDGE_CONTAINER" \
        $runtime_flag \
        $display_flag \
        --network host \
        --restart always \
        "$EDGE_IMAGE" \
        "${run_args[@]}" > /dev/null

    sleep 2
    if docker ps --filter "name=^/${EDGE_CONTAINER}$" --filter "status=running" | grep -q "${EDGE_CONTAINER}"; then
        echo -e "${GREEN}[SUCCESS] EYE-D 엣지 서비스 컨테이너가 성공적으로 가동되었습니다.${NC}"
        echo -e "실시간 로그를 확인하려면 아래 명령을 실행하십시오:"
        echo -e "  $0 logs -f"
    else
        echo -e "${RED}[ERROR] 컨테이너 구동 실패! 'docker logs $EDGE_CONTAINER'로 에러를 파악하십시오.${NC}"
    fi
    echo "========================================================"
}

# 서비스 중지
stop_services() {
    check_docker
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Jetson Edge 서비스 컨테이너 종료${NC}"
    echo "========================================================"
    
    # 엣지 서비스 정지
    if docker ps -a --filter "name=^/${EDGE_CONTAINER}$" | grep -q "${EDGE_CONTAINER}"; then
        echo -e "${YELLOW}[Edge] $EDGE_CONTAINER 컨테이너를 중지하고 제거합니다...${NC}"
        docker rm -f "$EDGE_CONTAINER" > /dev/null 2>&1
        echo -e "${GREEN}[SUCCESS] 엣지 서비스 컨테이너가 제거되었습니다.${NC}"
    else
        echo -e "[INFO] 실행 중이거나 정지된 엣지 서비스 컨테이너가 없습니다."
    fi

    # Qdrant DB 정지
    if docker ps -a --filter "name=^/${QDRANT_CONTAINER}$" | grep -q "${QDRANT_CONTAINER}"; then
        echo -e "${YELLOW}[Qdrant] $QDRANT_CONTAINER 컨테이너를 중지하고 제거합니다...${NC}"
        docker rm -f "$QDRANT_CONTAINER" > /dev/null 2>&1
        echo -e "${GREEN}[SUCCESS] Qdrant DB 컨테이너가 제거되었습니다.${NC}"
    else
        echo -e "[INFO] 실행 중이거나 정지된 Qdrant 컨테이너가 없습니다."
    fi
    
    # xhost 디스플레이 권한 기본 복구
    if command -v xhost &> /dev/null; then
        xhost -local:docker > /dev/null 2>&1
    fi

    echo "========================================================"
}

# 구동 상태 보기
show_status() {
    check_docker
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Jetson Edge 서비스 구동 상태${NC}"
    echo "========================================================"
    
    # 1. 컨테이너 Running 상태 출력
    local running_edge=$(docker ps -f "name=^/${EDGE_CONTAINER}$" --format "{{.Status}}")
    local running_qdrant=$(docker ps -f "name=^/${QDRANT_CONTAINER}$" --format "{{.Status}}")

    if [ -n "$running_edge" ]; then
        echo -e "1. 엣지 서비스 ($EDGE_CONTAINER): ${GREEN}RUNNING (${running_edge})${NC}"
    else
        echo -e "1. 엣지 서비스 ($EDGE_CONTAINER): ${RED}STOPPED${NC}"
    fi

    if [ -n "$running_qdrant" ]; then
        echo -e "2. Qdrant DB ($QDRANT_CONTAINER):    ${GREEN}RUNNING (${running_qdrant})${NC}"
    else
        echo -e "2. Qdrant DB ($QDRANT_CONTAINER):    ${RED}STOPPED${NC}"
    fi
    
    echo ""
    echo "3. 전체 Docker 컨테이너 현황:"
    docker ps -a --filter "name=${EDGE_CONTAINER}" --filter "name=${QDRANT_CONTAINER}"
    
    # 4. 하드웨어 간략 모니터링 (jtop이 지원되지 않는 임베디드 기본 상태 표시)
    if command -v nvidia-smi &> /dev/null; then
        echo ""
        echo "4. GPU 정보:"
        nvidia-smi --query-gpu=gpu_name,utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv
    elif [ -f "/sys/devices/gpu.0/load" ]; then
        echo ""
        echo "4. Jetson GPU 사용량:"
        local gpu_load=$(cat /sys/devices/gpu.0/load)
        echo -e "GPU Load: $((gpu_load / 10)).$((gpu_load % 10))%"
    fi
    echo "========================================================"
}

# 로그 모니터링
show_logs() {
    check_docker
    local target_container=""
    if [ "$LOG_SERVICE" == "edge" ]; then
        target_container="$EDGE_CONTAINER"
    elif [ "$LOG_SERVICE" == "qdrant" ]; then
        target_container="$QDRANT_CONTAINER"
    else
        echo -e "${RED}[ERROR] 유효하지 않은 서비스 명입니다. (edge 또는 qdrant 가능)${NC}"
        exit 1
    fi

    if ! docker ps -a --filter "name=^/${target_container}$" | grep -q "${target_container}"; then
        echo -e "${RED}[ERROR] $target_container 컨테이너가 생성되지 않아 로그를 볼 수 없습니다.${NC}"
        exit 1
    fi

    echo "========================================================"
    echo -e "   ${BLUE}서비스 로그 출력: $target_container${NC}"
    echo "========================================================"
    if [ "$FOLLOW_LOGS" = true ]; then
        docker logs -f "$target_container"
    else
        docker logs --tail 100 "$target_container"
    fi
}

# 데이터 초기화 및 삭제 (Cleanup)
cleanup_services() {
    echo -e "${RED}⚠️  주의: 이 작업은 컨테이너를 중지하고 모든 로컬 벡터 데이터 및 통신 캐시를 완전히 물리 삭제합니다.${NC}"
    read -p "계속 진행하시겠습니까? (y/N): " confirm
    case "$confirm" in
        y|Y )
            # 1. 우선 가동 중인 서비스 중지
            stop_services

            echo "========================================================"
            echo -e "   ${BLUE}로컬 데이터 및 네트워크 임시 버퍼 캐시 완전 초기화${NC}"
            echo "========================================================"

            # 2. Qdrant 로컬 볼륨 폴더 삭제
            if [ -d "$EDGE_DIR/qdrant_storage" ]; then
                echo -e "${YELLOW}[Cleanup] Qdrant 로컬 저장 데이터 폴더 제거...${NC}"
                rm -rf "$EDGE_DIR/qdrant_storage"
                echo -e "  -> $EDGE_DIR/qdrant_storage 삭제 완료"
            fi

            # 3. SQLite 오프라인 전송 지연 버퍼 삭제
            # main.py에서 생성하는 로컬 SQLite db
            local db_files=("$EDGE_DIR/edge_resilience_buffer.db" "$EDGE_DIR/edge_resilience_buffer.db-journal" "$EDGE_DIR/edge_resilience_buffer.db-wal")
            for f in "${db_files[@]}"; do
                if [ -f "$f" ]; then
                    echo -e "${YELLOW}[Cleanup] 로컬 SQLite 전송 버퍼 제거: $f...${NC}"
                    rm -f "$f"
                fi
            done
            
            # 4. (선택사항) 빌드된 임베디드 모델 캐시 (.onnx, .engine)
            # Jetson에서는 TensorRT 엔진 재빌드 시 수 분이 소요되므로, 
            # 기본적으로는 보존하고 명시적으로 삭제할 수 있도록 프롬프트 제공
            echo ""
            read -p "빌드된 TensorRT 엔진(.engine) 및 ONNX(.onnx) 모델 파일까지 삭제하시겠습니까? (y/N): " clean_models
            case "$clean_models" in
                y|Y )
                    echo -e "${YELLOW}[Cleanup] 변환 및 최적화된 모델 가중치 파일 제거...${NC}"
                    find "$EDGE_DIR" -name "*.engine" -delete
                    find "$EDGE_DIR" -name "*.onnx" -delete
                    echo -e "  -> .engine 및 .onnx 파일 삭제 완료"
                    ;;
                * )
                    echo -e "${GREEN}[Keep] 변환된 모델 파일은 보존합니다. (다음 실행 시 로드 지연 방지)${NC}"
                    ;;
            esac

            echo -e "${GREEN}[SUCCESS] 시스템 초기화 작업이 정상 완료되었습니다.${NC}"
            echo "========================================================"
            ;;
        * )
            echo -e "${GREEN}[Keep] 작업을 취소하고 중단합니다.${NC}"
            exit 0
            ;;
    esac
}

# 파라미터 처리
ACTION="$1"
shift # 액션 인자 제거하고 옵션들만 남김

# 명령어 분기 처리
case "$ACTION" in
    start)
        # start 액션에 대한 옵션 파싱
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -s|--source)
                    SOURCE="$2"
                    shift 2
                    ;;
                -c|--camera-id)
                    CAMERA_ID="$2"
                    shift 2
                    ;;
                -u|--server-url)
                    SERVER_URL="$2"
                    shift 2
                    ;;
                -d|--display)
                    DISPLAY_ON=true
                    shift
                    ;;
                --dry-run)
                    DRY_RUN=true
                    shift
                    ;;
                -h|--help)
                    show_help
                    exit 0
                    ;;
                *)
                    echo -e "${RED}알 수 없는 옵션입니다: $1${NC}"
                    show_help
                    exit 1
                    ;;
            esac
        done
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        # restart 액션에 대한 옵션 파싱
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -s|--source)
                    SOURCE="$2"
                    shift 2
                    ;;
                -c|--camera-id)
                    CAMERA_ID="$2"
                    shift 2
                    ;;
                -u|--server-url)
                    SERVER_URL="$2"
                    shift 2
                    ;;
                -d|--display)
                    DISPLAY_ON=true
                    shift
                    ;;
                --dry-run)
                    DRY_RUN=true
                    shift
                    ;;
                *)
                    echo -e "${RED}알 수 없는 옵션입니다: $1${NC}"
                    show_help
                    exit 1
                    ;;
            esac
        done
        stop_services
        start_services
        ;;
    status)
        show_status
        ;;
    logs)
        # logs 액션에 대한 옵션 파싱
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -f|--follow)
                    FOLLOW_LOGS=true
                    shift
                    ;;
                --service)
                    LOG_SERVICE="$2"
                    shift 2
                    ;;
                *)
                    echo -e "${RED}알 수 없는 옵션입니다: $1${NC}"
                    show_help
                    exit 1
                    ;;
            esac
        done
        show_logs
        ;;
    build)
        build_image
        ;;
    cleanup)
        cleanup_services
        ;;
    -h|--help|"")
        show_help
        ;;
    *)
        echo -e "${RED}알 수 없는 명령어: $ACTION${NC}"
        show_help
        exit 1
        ;;
esac
