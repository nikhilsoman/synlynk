"""In-flight token and spend circuit breaker engines."""

import os
import signal
import subprocess
import time
from typing import Iterator, Any, Optional
from token_breaker.models import CircuitBreakerError, RepetitionStallError, BreakerBudget


class TokenCircuitBreaker:
    """Monitors and bounds token usage and execution spend."""

    def __init__(self, budget: BreakerBudget):
        self.budget = budget
        self.accumulated_tokens: int = 0
        self.accumulated_cost_usd: float = 0.0
        self.consecutive_errors: int = 0

    def record_usage(self, tokens: int, cost_usd: float = 0.0) -> None:
        """Record usage and trip breaker if threshold breached."""
        self.accumulated_tokens += tokens
        self.accumulated_cost_usd += cost_usd

        if self.budget.max_tokens is not None and self.accumulated_tokens > self.budget.max_tokens:
            raise CircuitBreakerError(
                f"Token budget exceeded: {self.accumulated_tokens} > {self.budget.max_tokens}"
            )
        if self.budget.max_cost_usd is not None and self.accumulated_cost_usd > self.budget.max_cost_usd:
            raise CircuitBreakerError(
                f"Spend budget exceeded: ${self.accumulated_cost_usd:.4f} > ${self.budget.max_cost_usd:.4f}"
            )

    def record_error(self) -> None:
        self.consecutive_errors += 1
        if self.consecutive_errors >= self.budget.max_consecutive_errors:
            raise RepetitionStallError(
                f"Repetition stall: {self.consecutive_errors} consecutive failures detected."
            )

    def record_success(self) -> None:
        self.consecutive_errors = 0

    def wrap_stream(
        self, stream: Iterator[Any], tokens_per_chunk: int = 1, cost_per_token: float = 0.0
    ) -> Iterator[Any]:
        """Wrap a streaming chunk generator with circuit breaker checks."""
        for chunk in stream:
            self.record_usage(tokens_per_chunk, tokens_per_chunk * cost_per_token)
            yield chunk

    def supervise_process(self, popen_obj: subprocess.Popen, timeout_seconds: Optional[int] = None) -> int:
        """Supervise a subprocess PID, enforcing clean shutdown if killed."""
        start_t = time.time()
        while popen_obj.poll() is None:
            if timeout_seconds and (time.time() - start_t) > timeout_seconds:
                # Terminate then kill
                popen_obj.terminate()
                try:
                    popen_obj.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    popen_obj.kill()
                raise CircuitBreakerError(f"Process timed out after {timeout_seconds}s")
            time.sleep(0.05)
        return popen_obj.returncode
