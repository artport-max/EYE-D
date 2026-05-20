"""WebSocket 알림 모니터 — 실제 영상 테스트 중 실시간 알림 확인용.

서버의 /api/v1/security/ws/alerts 채널에 붙어
intrusion / vip_visit / regular_visit 알림을 콘솔에 출력한다.

실행 (Windows PowerShell):
    위치: EYE-D/server, (.venv) 활성 상태
    python tools\ws_monitor.py

실행 (Linux/macOS):
    위치: EYE-D/server, (.venv) 활성 상태
    python tools/ws_monitor.py

서버가 다른 호스트에 떠 있으면 --host 로 지정:
    python tools/ws_monitor.py --host 192.168.0.10 --port 8000

의존성:
    pip install websockets
    (requirements.txt 에 포함되어 있음)
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime

import websockets


# ANSI 색상 (Windows Terminal / PowerShell 7 / VS Code 에서 잘 보임)
RESET = "\033[0m"
RED   = "\033[91m"
YEL   = "\033[93m"
GRN   = "\033[92m"
CYAN  = "\033[96m"
DIM   = "\033[2m"


def color_for(alert_type: str) -> str:
    return {
        "intrusion":      RED,
        "vip_visit":      YEL,
        "regular_visit":  GRN,
    }.get(alert_type, CYAN)


def fmt_alert(msg: dict) -> str:
    """알림 한 건을 사람이 읽기 좋은 형태로."""
    t = msg.get("type", "?")
    color = color_for(t)
    ts = datetime.now().strftime("%H:%M:%S")
    head = f"{color}[{ts}] {t.upper():<14}{RESET}"
    detail = " ".join(f"{k}={v}" for k, v in msg.items() if k != "type")
    return f"{head} {detail}"


async def monitor(host: str, port: int, path: str) -> None:
    url = f"ws://{host}:{port}{path}"
    print(f"{DIM}[ws_monitor] connecting to {url} ...{RESET}")

    while True:
        try:
            async with websockets.connect(url) as ws:
                print(f"{GRN}[ws_monitor] connected. waiting for alerts...{RESET}")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        print(fmt_alert(msg))
                    except json.JSONDecodeError:
                        print(f"{DIM}[raw] {raw}{RESET}")
        except (ConnectionRefusedError, OSError) as e:
            print(f"{RED}[ws_monitor] connection failed: {e}. retrying in 3s...{RESET}")
            await asyncio.sleep(3)
        except websockets.ConnectionClosed:
            print(f"{YEL}[ws_monitor] connection closed. reconnecting...{RESET}")
            await asyncio.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="EYE-D WebSocket alert monitor")
    parser.add_argument("--host", default="127.0.0.1", help="서버 호스트 (기본: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본: 8000)")
    parser.add_argument("--path", default="/api/v1/security/ws/alerts",
                        help="WebSocket 경로 (기본: /api/v1/security/ws/alerts)")
    args = parser.parse_args()

    try:
        asyncio.run(monitor(args.host, args.port, args.path))
    except KeyboardInterrupt:
        print(f"\n{DIM}[ws_monitor] stopped by user.{RESET}")


if __name__ == "__main__":
    main()
