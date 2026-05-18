"""
null_objects.py
---------------
Null Object 패턴 구현체.

외부 의존성(Qdrant, HTTP 서버)이 없거나 주입되지 않을 때
파이프라인이 예외 없이 계속 동작하도록 보장합니다.

사용 목적:
  - 개발/테스트 환경에서 실제 서버 없이 파이프라인 실행
  - 서버 장애 시 Edge가 멈추지 않도록 폴백 제공
  - `None` 체크 분기를 제거하여 코드 단순화

설계 원칙 (Null Object Pattern):
  실제 객체와 동일한 인터페이스를 구현하되,
  모든 동작을 "아무것도 안 함 + 경고 로그"로 처리합니다.
"""

import logging

logger = logging.getLogger(__name__)


class NullDBClient:
    """DB 클라이언트가 없을 때의 Null Object.

    VectorDBClient와 동일한 인터페이스를 구현합니다.
    모든 쓰기 작업은 WARNING 로그만 남기고 무시합니다.

    Usage:
        # PipelineRunner가 내부적으로 사용 (직접 생성할 필요 없음)
        runner = PipelineRunner()  # db_client 미주입 시 NullDBClient 자동 사용
    """

    def connect(self, *args, **kwargs) -> bool:
        logger.warning(
            "NullDBClient: DB client not configured. "
            "Pass a VectorDBClient instance to PipelineRunner to enable vector storage."
        )
        return False

    def collection_exists(self, collection_name: str) -> bool:
        return False

    def ensure_collection(self, collection_name: str, vector_size: int = 512):
        pass  # 아무것도 안 함

    def upsert(self, collection_name: str, records: list, vector_size: int = 512) -> bool:
        logger.debug(
            f"NullDBClient: skipping upsert of {len(records)} record(s) "
            f"into '{collection_name}' (no DB configured)."
        )
        return False

    def search(self, collection_name: str, query_vector: list, top_k: int = 10) -> dict:
        logger.debug("NullDBClient: skipping search (no DB configured).")
        return {'hits': [], 'latency_ms': 0.0, 'top_k': top_k, 'hit_count': 0}

    def index_exists(self, collection_name: str) -> bool:
        return False


class NullSender:
    """HTTP 서버 전송 클라이언트가 없을 때의 Null Object.

    ServerSender와 동일한 인터페이스를 구현합니다.
    모든 전송 요청은 WARNING 로그만 남기고 무시합니다.

    Usage:
        # PipelineRunner가 내부적으로 사용 (직접 생성할 필요 없음)
        runner = PipelineRunner()  # http_sender 미주입 시 NullSender 자동 사용
    """

    def post(self, endpoint: str, payload: dict) -> tuple:
        """HTTP POST 요청을 무시합니다.

        Returns:
            (0, {}) — 전송되지 않았음을 나타내는 더미 응답.
        """
        track_count = len(payload.get('tracks', []))
        logger.debug(
            f"NullSender: skipping POST to '{endpoint}' "
            f"({track_count} track(s), no server configured)."
        )
        return 0, {}

    def send_vectors(self, *args, **kwargs) -> bool:
        logger.debug("NullSender: skipping send_vectors (no server configured).")
        return False

    def send_event(self, *args, **kwargs) -> bool:
        logger.debug("NullSender: skipping send_event (no server configured).")
        return False

    def send_heartbeat(self, *args, **kwargs) -> bool:
        logger.debug("NullSender: skipping send_heartbeat (no server configured).")
        return False
