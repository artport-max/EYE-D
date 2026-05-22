#!/bin/bash

# ==============================================================================
# EYE-D Central Server 통합 관리 스크립트 (manage_server.sh)
#
# 역할: 중앙 서버 환경에서 Docker 기반 PostgreSQL(pgvector) DB 및 
#       FastAPI 백엔드 서버의 구동(start), 중지(stop), 모니터링(logs, status),
#       초기화(cleanup)를 통합적으로 관리합니다.
# ==============================================================================

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SERVER_DIR/uvicorn.log"

# 이동
cd "$SERVER_DIR"

# 기본 설정값
HOST="0.0.0.0"
PORT="8000"
CONDA_ENV_NAME="eyed-server"

# 도움말 출력 함수
show_help() {
    echo -e "${BLUE}EYE-D Central Server 관리 도구${NC}"
    echo "사용법: $0 [Command] [Options]"
    echo ""
    echo "명령어(Command):"
    echo "  start       PostgreSQL DB 및 FastAPI 백엔드 서버를 백그라운드에서 구동합니다."
    echo "  stop        구동 중인 FastAPI 서버 및 DB 컨테이너를 중지합니다."
    echo "  restart     서비스를 재시작합니다 (stop 후 start)."
    echo "  status      서버 및 DB의 현재 구동 상태를 확인합니다."
    echo "  logs        FastAPI 서버 로그(uvicorn.log)를 출력합니다."
    echo "  cleanup     서비스를 중지하고 로그 및 데이터베이스 볼륨을 완전히 삭제하여 초기화합니다."
    echo ""
    echo "옵션(Options) [start / restart 시 사용 가능]:"
    echo "  --host <ip>        바인딩할 호스트 IP (기본값: $HOST)"
    echo "  --port <port>      바인딩할 포트 번호 (기본값: $PORT)"
    echo ""
    echo "옵션(Options) [logs 시 사용 가능]:"
    echo "  -f, --follow       실시간 로그 흐름(tail -f)을 모니터링합니다."
    echo ""
    echo "예시(Examples):"
    echo "  * 기본 시작:          $0 start"
    echo "  * 외부 접속 허용 시작:  $0 start --host 0.0.0.0 --port 8000"
    echo "  * 로그 실시간 모니터링: $0 logs -f"
    echo "  * 시스템 완전 초기화:   $0 cleanup"
}

# Docker 권한 체크 및 실행 커맨드 정의
get_docker_cmd() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}[ERROR] Docker가 설치되어 있지 않거나 PATH에 존재하지 않습니다.${NC}"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        echo "sudo"
    else
        echo ""
    fi
}

# 가상환경 활성화
activate_env() {
    # Conda 베이스 경로 찾기
    CONDA_BASE=$(conda info --base 2>/dev/null)

    if [ -n "$CONDA_BASE" ] && [ -d "$CONDA_BASE/envs/$CONDA_ENV_NAME" ]; then
        echo -e " -> Conda 환경 발견: ${GREEN}$CONDA_ENV_NAME${NC}"
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        conda activate "$CONDA_ENV_NAME"
    elif [ -d ".venv" ]; then
        echo -e " -> 로컬 가상환경(.venv) 발견. 활성화 중..."
        source .venv/bin/activate
    else
        echo -e "${YELLOW}[WARNING] Conda 환경 '$CONDA_ENV_NAME' 또는 '.venv'를 찾을 수 없습니다.${NC}"
        echo -e " -> 시스템 기본 python/uvicorn을 사용합니다."
    fi
}

# 서비스 시작
start_server() {
    local sudo_prefix=$(get_docker_cmd)
    
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Central Server 서비스 구동 시작${NC}"
    echo "========================================================"

    # 1. DB 기동
    echo -e "[1/3] ${YELLOW}데이터베이스 컨테이너 기동 중...${NC}"
    if [ -n "$sudo_prefix" ]; then
        sudo docker compose up -d
    else
        docker compose up -d
    fi
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] 데이터베이스 기동에 실패했습니다.${NC}"
        exit 1
    fi
    echo -e "${GREEN} -> 데이터베이스 기동 완료.${NC}"

    # 2. FastAPI 서버 중복 실행 확인
    if [ -f "$PID_FILE" ]; then
        local old_pid=$(cat "$PID_FILE")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}[WARNING] FastAPI 서버가 이미 실행 중입니다. (PID: $old_pid)${NC}"
            echo -e "재시작하려면 '$0 restart'를 실행하세요."
            exit 0
        else
            # 유효하지 않은 PID 파일 정리
            rm -f "$PID_FILE"
        fi
    fi

    # 3. 가상환경 활성화
    echo -e "[2/3] ${YELLOW}Python 가상환경 활성화 중...${NC}"
    activate_env

    # 4. FastAPI 백그라운드 실행
    echo -e "[3/3] ${YELLOW}FastAPI 서버 백그라운드 기동 중 (http://$HOST:$PORT)...${NC}"
    
    nohup uvicorn app.main:app --host "$HOST" --port "$PORT" --reload > "$LOG_FILE" 2>&1 &
    local server_pid=$!
    echo "$server_pid" > "$PID_FILE"
    
    sleep 2
    if ps -p "$server_pid" > /dev/null 2>&1; then
        echo -e "${GREEN}[SUCCESS] EYE-D 백엔드 서버가 성공적으로 가동되었습니다. (PID: $server_pid)${NC}"
        echo -e "실시간 로그를 확인하려면 아래 명령을 실행하십시오:"
        echo -e "  $0 logs -f"
    else
        echo -e "${RED}[ERROR] 서버 구동 실패! '$LOG_FILE'에서 에러 내용을 파악하십시오.${NC}"
        rm -f "$PID_FILE"
    fi
    echo "========================================================"
}

# 서비스 중지
stop_server() {
    local sudo_prefix=$(get_docker_cmd)
    
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Central Server 서비스 종료${NC}"
    echo "========================================================"

    # 1. FastAPI 서버 중지
    if [ -f "$PID_FILE" ]; then
        local server_pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}[Server] FastAPI 서버(PID: $server_pid)를 종료합니다...${NC}"
        
        # uvicorn 프로세스 및 그 자식(reload) 프로세스까지 트리 형태로 종료 시도
        pkill -P "$server_pid" > /dev/null 2>&1
        kill "$server_pid" > /dev/null 2>&1
        sleep 1
        
        if ps -p "$server_pid" > /dev/null 2>&1; then
            echo -e " -> 강제 종료를 시도합니다..."
            kill -9 "$server_pid" > /dev/null 2>&1
        fi
        
        rm -f "$PID_FILE"
        echo -e "${GREEN}[SUCCESS] FastAPI 서버가 종료되었습니다.${NC}"
    else
        # PID 파일은 없지만 돌고 있는 uvicorn이 있는지 확인 및 정리
        local stray_pids=$(pgrep -f "uvicorn app.main:app")
        if [ -n "$stray_pids" ]; then
            echo -e "${YELLOW}[Server] 감지된 uvicorn 프로세스를 정리합니다...${NC}"
            pkill -f "uvicorn app.main:app" > /dev/null 2>&1
            echo -e "${GREEN}[SUCCESS] 감지된 프로세스가 정리되었습니다.${NC}"
        else
            echo -e "[INFO] 실행 중인 FastAPI 서버가 없습니다."
        fi
    fi

    # 2. DB 컨테이너 중지
    echo -e "\n[DB] 데이터베이스 컨테이너를 중지합니다..."
    if [ -n "$sudo_prefix" ]; then
        sudo docker compose down
    else
        docker compose down
    fi
    echo -e "${GREEN}[SUCCESS] 데이터베이스 컨테이너가 중지 및 제거되었습니다.${NC}"
    echo "========================================================"
}

# 구동 상태 확인
show_status() {
    local sudo_prefix=$(get_docker_cmd)
    
    echo "========================================================"
    echo -e "   ${BLUE}EYE-D Central Server 구동 상태${NC}"
    echo "========================================================"

    # 1. FastAPI 서버 상태
    if [ -f "$PID_FILE" ]; then
        local server_pid=$(cat "$PID_FILE")
        if ps -p "$server_pid" > /dev/null 2>&1; then
            echo -e "1. 백엔드 서버 (FastAPI): ${GREEN}RUNNING (PID: $server_pid)${NC}"
        else
            echo -e "1. 백엔드 서버 (FastAPI): ${RED}STOPPED (유효하지 않은 PID 파일 존재)${NC}"
        fi
    else
        echo -e "1. 백엔드 서버 (FastAPI): ${RED}STOPPED${NC}"
    fi

    # 2. DB 상태
    local running_db=""
    if [ -n "$sudo_prefix" ]; then
        running_db=$(sudo docker ps -f "name=^/eyed-postgres$" --format "{{.Status}}")
    else
        running_db=$(docker ps -f "name=^/eyed-postgres$" --format "{{.Status}}")
    fi

    if [ -n "$running_db" ]; then
        echo -e "2. 데이터베이스 (PostgreSQL): ${GREEN}RUNNING (${running_db})${NC}"
    else
        echo -e "2. 데이터베이스 (PostgreSQL): ${RED}STOPPED${NC}"
    fi

    echo ""
    echo "3. 전체 Docker 컨테이너 현황:"
    if [ -n "$sudo_prefix" ]; then
        sudo docker ps -a --filter "name=eyed-postgres"
    else
        docker ps -a --filter "name=eyed-postgres"
    fi
    echo "========================================================"
}

# 로그 모니터링
show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}[ERROR] 로그 파일($LOG_FILE)이 존재하지 않습니다. 서버를 먼저 기동해 주세요.${NC}"
        exit 1
    fi

    echo "========================================================"
    echo -e "   ${BLUE}FastAPI 백엔드 서버 로그 출력 (uvicorn.log)${NC}"
    echo "========================================================"
    if [ "$FOLLOW_LOGS" = true ]; then
        tail -f "$LOG_FILE"
    else
        tail -n 100 "$LOG_FILE"
    fi
}

# 데이터 초기화 및 삭제 (Cleanup)
cleanup_server() {
    echo -e "${RED}⚠️  주의: 이 작업은 서비스를 중지하고 로그 및 데이터베이스 볼륨(모든 데이터)을 완전히 삭제하여 초기화합니다.${NC}"
    read -p "계속 진행하시겠습니까? (y/N): " confirm
    case "$confirm" in
        y|Y )
            # 1. 서비스 중지
            stop_server

            echo "========================================================"
            echo -e "   ${BLUE}데이터베이스 볼륨 및 로그 파일 완전 초기화${NC}"
            echo "========================================================"

            # 2. uvicorn.log 삭제
            if [ -f "$LOG_FILE" ]; then
                echo -e "${YELLOW}[Cleanup] uvicorn.log 로그 파일 제거...${NC}"
                rm -f "$LOG_FILE"
            fi

            # 3. Docker DB 볼륨 포함 완전 삭제
            echo -e "${YELLOW}[Cleanup] 데이터베이스 컨테이너 및 볼륨 물리 삭제 중...${NC}"
            local sudo_prefix=$(get_docker_cmd)
            if [ -n "$sudo_prefix" ]; then
                sudo docker compose down -v
            else
                docker compose down -v
            fi

            echo -e "${GREEN}[SUCCESS] 시스템 초기화 작업이 완료되었습니다.${NC}"
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
                --host)
                    HOST="$2"
                    shift 2
                    ;;
                --port)
                    PORT="$2"
                    shift 2
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
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        # restart 액션에 대한 옵션 파싱
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --host)
                    HOST="$2"
                    shift 2
                    ;;
                --port)
                    PORT="$2"
                    shift 2
                    ;;
                *)
                    echo -e "${RED}알 수 없는 옵션입니다: $1${NC}"
                    show_help
                    exit 1
                    ;;
            esac
        done
        stop_server
        start_server
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
                *)
                    echo -e "${RED}알 수 없는 옵션입니다: $1${NC}"
                    show_help
                    exit 1
                    ;;
            esac
        done
        show_logs
        ;;
    cleanup)
        cleanup_server
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
