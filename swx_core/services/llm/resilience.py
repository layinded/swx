import asyncio
import random
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable
from swx_core.utils.time import utc_now

class CircuitOpenError(RuntimeError):
    pass

class LLMTimeoutError(TimeoutError):
    pass

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int, success_threshold: int, recovery_timeout_seconds: int):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None

    def allow_request(self) -> bool:
        if self.state != CircuitState.OPEN:
            return True
        if self.last_failure_time and utc_now() >= self.last_failure_time + timedelta(seconds=self.recovery_timeout_seconds):
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = utc_now()
        self.success_count = 0
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

class CircuitBreakerRegistry:
    _registry: dict[str, CircuitBreaker] = {}

    @classmethod
    def get(cls, name: str, failure_threshold: int = 5, success_threshold: int = 1, recovery_timeout_seconds: int = 30) -> CircuitBreaker:
        if name not in cls._registry:
            cls._registry[name] = CircuitBreaker(name, failure_threshold, success_threshold, recovery_timeout_seconds)
        return cls._registry[name]

    @classmethod
    def reset(cls, name: str | None = None) -> None:
        if name is None:
            cls._registry.clear()
            return
        cls._registry.pop(name, None)

    @classmethod
    def all_states(cls) -> dict[str, str]:
        return {name: breaker.state.value for name, breaker in cls._registry.items()}

def calculate_backoff(attempt: int, base_delay: float, max_delay: float, jitter: bool = True) -> float:
    delay = min(max_delay, base_delay * (2 ** max(attempt - 1, 0)))
    if not jitter:
        return delay
    return delay + random.uniform(0, delay / 4)

async def retry_with_backoff(
    fn: Callable[[], Awaitable[Any]], max_retries: int, base_delay: float, max_delay: float, circuit_breaker: CircuitBreaker | None = None,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):
        if circuit_breaker and not circuit_breaker.allow_request():
            raise CircuitOpenError(f"Circuit open for {circuit_breaker.name}")
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt > max_retries:
                break
            await asyncio.sleep(calculate_backoff(attempt, base_delay, max_delay, True))
    if last_error is None:
        raise RuntimeError("Retry failed without captured exception")
    raise last_error

async def call_with_timeout(fn: Callable[[], Awaitable[Any]], timeout_seconds: int, provider_name: str) -> Any:
    try:
        return await asyncio.wait_for(fn(), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise LLMTimeoutError(f"Timed out while calling provider '{provider_name}'") from exc
