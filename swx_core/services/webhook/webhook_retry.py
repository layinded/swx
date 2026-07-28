"""Retry helpers for outbound webhooks."""

from datetime import datetime, timedelta, timezone
from collections.abc import Awaitable, Callable
from typing import Any

from swx_core.config.settings import WEBHOOK_CIRCUIT_BREAKER_THRESHOLD
from swx_core.services.llm.resilience import CircuitBreaker, CircuitBreakerRegistry, call_with_timeout, retry_with_backoff


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def should_retry(response_status_code: int | None, error_message: str | None, attempt_count: int, max_retries: int) -> bool:
    if attempt_count >= max_retries:
        return False
    if error_message or response_status_code is None:
        return True
    return response_status_code in {408, 409, 425, 429} or response_status_code >= 500


def get_retry_delay(base_delay: int, attempt_count: int) -> int:
    backoff_multiplier = 2 ** max(attempt_count - 1, 0)
    return min(base_delay * backoff_multiplier, base_delay * 16)


def calculate_next_retry(base_delay: int, attempt_count: int) -> datetime:
    return utc_now_naive() + timedelta(seconds=get_retry_delay(base_delay, attempt_count))


def get_circuit_breaker(endpoint_id: str) -> CircuitBreaker:
    return CircuitBreakerRegistry.get(f"webhook:{endpoint_id}", failure_threshold=WEBHOOK_CIRCUIT_BREAKER_THRESHOLD, success_threshold=1, recovery_timeout_seconds=30)


async def run_with_resilience(fn: Callable[[], Awaitable[Any]], *, endpoint_id: str, timeout_seconds: int) -> Any:
    breaker = get_circuit_breaker(endpoint_id)

    async def send_once() -> Any:
        return await call_with_timeout(fn, timeout_seconds, endpoint_id)

    return await retry_with_backoff(send_once, 1, 0.5, 4.0, breaker)
