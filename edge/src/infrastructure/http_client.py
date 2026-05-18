"""
http_client.py
--------------
FastAPI 백엔드 서버와 통신하는 HTTP 클라이언트 구현체.
네트워크 불안정 또는 서버 장애에 대비하여 로컬 SQLite DB 기반의 버퍼링 및 자동 재전송(Resilience) 메커니즘을 내장하고 있습니다.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Tuple, Dict, Any
import requests

logger = logging.getLogger(__name__)


class ResilientServerSender:
    """네트워크 복원력을 갖춘 서버 전송 클라이언트.

    전송 요청(post)이 들어오면 우선 로컬 SQLite DB 버퍼에 적재(Enqueue)합니다.
    백그라운드 스레드가 이 버퍼를 감시하며 순차적으로 서버로 안전하게 전송을 시도합니다.
    전송 성공 시 버퍼에서 해당 데이터를 삭제하고, 실패 시 통신이 회복될 때까지 데이터를 안전하게 보존합니다.
    """

    def __init__(self, base_url: str = 'http://localhost:8000', db_path: str = 'edge_resilience_buffer.db', retry_interval: float = 5.0):
        """
        Args:
            base_url: FastAPI 백엔드 서버의 Base URL (예: 'http://localhost:8000')
            db_path: 로컬 SQLite 버퍼 데이터베이스 파일 경로
            retry_interval: 재전송 시도 주기 (초 단위)
        """
        self.base_url = base_url.rstrip('/')
        self.db_path = db_path
        self.retry_interval = retry_interval
        
        self.running = False
        self.sender_thread: threading.Thread = None
        self._lock = threading.Lock()
        
        # SQLite 버퍼 테이블 초기화
        self._init_db()
        
        # 백그라운드 재전송 스레드 기동
        self.start()

    def _init_db(self):
        """로컬 SQLite 버퍼 테이블이 없으면 생성합니다."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS send_buffer (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        endpoint TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        retry_count INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
            logger.info(f"Resilient buffer SQLite database initialized at '{self.db_path}'")
        except Exception as e:
            logger.error(f"Failed to initialize resilient SQLite buffer database: {e}")
            raise

    def start(self):
        """백그라운드 전송 및 재시도 루프를 시작합니다."""
        if self.running:
            return
        
        self.running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, name="ResilientSenderThread", daemon=True)
        self.sender_thread.start()
        logger.info("Resilient backup sender thread started.")

    def stop(self):
        """백그라운드 스레드를 정지합니다."""
        self.running = False
        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join(timeout=3.0)
        logger.info("Resilient backup sender thread stopped.")

    def post(self, endpoint: str, payload: dict) -> Tuple[int, Dict[str, Any]]:
        """서버 전송 요청을 수행합니다.
        데이터를 먼저 로컬 SQLite 큐에 밀어넣고(Enqueue), 성공을 대기하도록 백그라운드를 기동합니다.

        Args:
            endpoint: 서버 API 엔드포인트 (예: '/api/v1/vectors')
            payload: JSON 직렬화가 가능한 전송 데이터

        Returns:
            (status_code, response_data) 튜플.
            버퍼에 정상 등록되면 status_code는 202(Accepted)로 임시 변환하여 응답합니다.
        """
        endpoint = '/' + endpoint.lstrip('/')
        
        try:
            payload_str = json.dumps(payload)
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO send_buffer (endpoint, payload, created_at) VALUES (?, ?, ?)",
                        (endpoint, payload_str, time.time())
                    )
                    conn.commit()
            
            logger.debug(f"Payload successfully buffered in local SQLite queue for endpoint '{endpoint}'")
            return 202, {"message": "Detections accepted and buffered locally"}
        except Exception as e:
            logger.error(f"Failed to write payload to local resilience buffer SQLite DB: {e}")
            # SQLite에 담을 수조차 없다면 즉시 동기 전송을 예비 시도
            return self._sync_post_direct(endpoint, payload)

    def _sync_post_direct(self, endpoint: str, payload: dict) -> Tuple[int, dict]:
        """로컬 DB 실패 시 서버로 즉각적인 동기식 예비 전송을 시도합니다."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=5.0)
            return response.status_code, response.json() if response.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Direct recovery POST to {url} failed: {e}")
            return 0, {"error": str(e)}

    def _sender_loop(self):
        """로컬 SQLite 큐에 적재된 페이로드들을 순차적으로 전송 및 소진하는 백그라운드 루프."""
        while self.running:
            try:
                # 버퍼에서 전송 대기 중인 가장 오래된 항목 1개 조회
                buffered_item = self._peek_buffer()
                
                if buffered_item is None:
                    # 보낼 항목이 없으면 슬립
                    time.sleep(1.0)
                    continue

                item_id, endpoint, payload_str, retry_count = buffered_item
                payload = json.loads(payload_str)
                url = f"{self.base_url}{endpoint}"

                # 동기식 전송 수행
                success = self._send_to_endpoint(url, payload)
                
                if success:
                    # 전송 성공 시 SQLite DB 버퍼에서 제거 (소진)
                    self._dequeue_buffer(item_id)
                    logger.info(
                        f"Successfully sent buffered item (ID={item_id}) to {url}. "
                        f"Buffer size decreased."
                    )
                else:
                    # 전송 실패 시 retry_count 증가시키고 일정 시간 슬립 후 대기
                    self._increment_retry_count(item_id)
                    logger.warning(
                        f"Failed to send buffered item (ID={item_id}) to {url}. "
                        f"Will retry after {self.retry_interval} seconds..."
                    )
                    time.sleep(self.retry_interval)

            except Exception as e:
                logger.error(f"Error inside resilient sender loop: {e}")
                time.sleep(self.retry_interval)

    def _send_to_endpoint(self, url: str, payload: dict) -> bool:
        """실제 HTTP POST 요청을 전송합니다."""
        try:
            response = requests.post(url, json=payload, timeout=5.0)
            if response.status_code in (200, 201):
                return True
            else:
                logger.warning(f"Server rejected payload (status={response.status_code}): {response.text}")
                return False
        except requests.RequestException as e:
            logger.debug(f"Network request exception during background transmission: {e}")
            return False

    def _peek_buffer(self) -> Tuple[int, str, str, int]:
        """버퍼에서 가장 오래된 데이터 레코드를 하나 반환합니다."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, endpoint, payload, retry_count FROM send_buffer ORDER BY created_at ASC LIMIT 1"
                    )
                    row = cursor.fetchone()
                    return row
        except Exception as e:
            logger.error(f"Error peeking SQLite buffer: {e}")
            return None

    def _dequeue_buffer(self, item_id: int):
        """전송이 완료된 항목을 큐에서 완전히 지웁니다."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM send_buffer WHERE id = ?", (item_id,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error deleting row from SQLite buffer: {e}")

    def _increment_retry_count(self, item_id: int):
        """전송 실패한 항목의 재시도 카운트를 누적시킵니다."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE send_buffer SET retry_count = retry_count + 1 WHERE id = ?", (item_id,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error updating retry count: {e}")

    def get_buffer_size(self) -> int:
        """현재 버퍼에 남아있는 미전송 페이로드 개수를 반환합니다."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM send_buffer")
                    count = cursor.fetchone()[0]
                    return count
        except Exception as e:
            logger.error(f"Error getting buffer count: {e}")
            return 0

    def clear_buffer(self):
        """버퍼의 모든 미전송 데이터를 제거하여 초기화합니다."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM send_buffer")
                    conn.commit()
            logger.info("Resilient backup send buffer cleared successfully.")
        except Exception as e:
            logger.error(f"Error clearing SQLite buffer: {e}")
