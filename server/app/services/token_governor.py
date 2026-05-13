import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenUsage:
    """하루치 사용 기록을 들고 다니는 단순 상태 컨테이너."""
    daily_used: int = 0
    day_started_at: float = field(default_factory=time.time)
    last_traces: list[dict] = field(default_factory=list)


class TokenBudgetExceeded(Exception):
    """한도 초과 시 던지는 전용 예외. 일반 Exception과 구분해 잡기 위함."""
    pass


class TokenGovernor:
    """단순 메모리 기반 토큰 사용량 관리기.
    실서비스에서는 Redis로 옮기되, 학습 단계에서는 메모리로 충분.
    arttrace의 모든 에이전트가 이 한 인스턴스를 공유한다.
    """

    def __init__(self):
        self.usage = TokenUsage()
        self.daily_budget = int(os.getenv("DAILY_TOKEN_BUDGET", "100000"))
        self.per_request_max = int(os.getenv("PER_REQUEST_MAX_TOKENS", "2000"))

    def _rotate_day_if_needed(self):
        """24시간 지나면 카운터를 자동으로 새 날로 초기화."""
        now = time.time()
        if now - self.usage.day_started_at > 86400:
            self.usage = TokenUsage(day_started_at=now)

    def request(self, agent: str, tokens_estimate: int,
                meta: Optional[dict] = None) -> str:
        """호출 전 호출. trace_id 발급 + 한도 검사.
        한도 초과면 TokenBudgetExceeded 예외 → 호출자가 잡아서 처리."""
        self._rotate_day_if_needed()
        if tokens_estimate > self.per_request_max:
            raise TokenBudgetExceeded(
                f"per-request limit: {tokens_estimate} > {self.per_request_max}"
            )
        if self.usage.daily_used + tokens_estimate > self.daily_budget:
            raise TokenBudgetExceeded(
                f"daily budget exceeded "
                f"({self.usage.daily_used}+{tokens_estimate}>{self.daily_budget})"
            )
        trace_id = uuid.uuid4().hex[:12]
        self.usage.last_traces.append({
            "trace_id": trace_id, "agent": agent,
            "estimate": tokens_estimate, "ts": time.time(),
            "meta": meta or {},
        })
        return trace_id

    def commit(self, trace_id: str, actual_tokens: int):
        """호출 후 실제 사용량 반영. 추정치와 실제치가 다를 수 있어 분리."""
        self.usage.daily_used += actual_tokens
        for t in reversed(self.usage.last_traces):
            if t["trace_id"] == trace_id:
                t["actual"] = actual_tokens
                break

    def stats(self) -> dict:
        """현재 상태 요약. /admin/tokens 엔드포인트에서 사용."""
        self._rotate_day_if_needed()
        return {
            "daily_used": self.usage.daily_used,
            "daily_budget": self.daily_budget,
            "remaining": self.daily_budget - self.usage.daily_used,
            "recent_traces": self.usage.last_traces[-10:],
        }


# 싱글턴 — 앱 어디서나 from ... import governor 한 줄로 같은 인스턴스 공유
governor = TokenGovernor()