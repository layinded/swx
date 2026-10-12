# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.services.llm.resilience — circuit breaker, retry, timeout."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.llm.resilience import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    LLMTimeoutError,
    calculate_backoff,
    call_with_timeout,
    retry_with_backoff,
)
from swx_core.utils.time import utc_now


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """Tests for the CircuitBreaker class and its state transitions."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self) -> None:
        """New circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker("test", failure_threshold=3, success_threshold=2, recovery_timeout_seconds=30)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_allow_request_when_closed(self) -> None:
        """allow_request returns True when circuit is CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=3, success_threshold=2, recovery_timeout_seconds=30)
        assert await cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_closed_to_open_transition(self) -> None:
        """Circuit transitions from CLOSED to OPEN after failure_threshold failures."""
        cb = CircuitBreaker("test", failure_threshold=3, success_threshold=2, recovery_timeout_seconds=30)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_allow_request_denied_when_open(self) -> None:
        """allow_request returns False when circuit is OPEN and timeout not elapsed."""
        cb = CircuitBreaker("test", failure_threshold=1, success_threshold=2, recovery_timeout_seconds=30)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert await cb.allow_request() is False

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self) -> None:
        """Circuit transitions from OPEN to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker("test", failure_threshold=1, success_threshold=2, recovery_timeout_seconds=0)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # recovery_timeout_seconds=0 means it's immediately eligible
        allowed = await cb.allow_request()
        assert allowed is True
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_after_success_threshold(self) -> None:
        """Circuit transitions from HALF_OPEN to CLOSED after success_threshold successes."""
        cb = CircuitBreaker("test", failure_threshold=1, success_threshold=2, recovery_timeout_seconds=0)
        await cb.record_failure()
        # Move to HALF_OPEN
        await cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_goes_back_to_open(self) -> None:
        """A failure in HALF_OPEN state transitions back to OPEN."""
        cb = CircuitBreaker("test", failure_threshold=1, success_threshold=2, recovery_timeout_seconds=0)
        await cb.record_failure()
        await cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_record_success_resets_failure_count(self) -> None:
        """record_success resets failure_count to 0."""
        cb = CircuitBreaker("test", failure_threshold=3, success_threshold=2, recovery_timeout_seconds=30)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.failure_count == 2
        await cb.record_success()
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_access_with_lock(self) -> None:
        """Concurrent access to the circuit breaker is serialized by the lock."""
        cb = CircuitBreaker("test", failure_threshold=5, success_threshold=2, recovery_timeout_seconds=30)

        async def fail_and_check() -> None:
            await cb.record_failure()

        # Run multiple concurrent failures
        await asyncio.gather(*(fail_and_check() for _ in range(10)))

        # All 10 failures should be recorded (no race condition)
        assert cb.failure_count == 10
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------

class TestCircuitBreakerRegistry:
    """Tests for the CircuitBreakerRegistry class."""

    def setup_method(self) -> None:
        """Reset the registry before each test."""
        CircuitBreakerRegistry.reset()

    def test_get_creates_new_breaker(self) -> None:
        """get() creates a new CircuitBreaker when name is not registered."""
        cb = CircuitBreakerRegistry.get("test-provider")
        assert cb is not None
        assert cb.name == "test-provider"
        assert cb.state == CircuitState.CLOSED

    def test_get_returns_existing_breaker(self) -> None:
        """get() returns the same CircuitBreaker for the same name."""
        cb1 = CircuitBreakerRegistry.get("test-provider")
        cb2 = CircuitBreakerRegistry.get("test-provider")
        assert cb1 is cb2

    def test_get_with_custom_params(self) -> None:
        """get() accepts custom thresholds."""
        cb = CircuitBreakerRegistry.get(
            "custom", failure_threshold=10, success_threshold=5, recovery_timeout_seconds=60
        )
        assert cb.failure_threshold == 10
        assert cb.success_threshold == 5
        assert cb.recovery_timeout_seconds == 60

    def test_reset_specific_name(self) -> None:
        """reset(name) removes a specific breaker."""
        CircuitBreakerRegistry.get("provider-a")
        CircuitBreakerRegistry.get("provider-b")
        CircuitBreakerRegistry.reset("provider-a")
        assert "provider-a" not in CircuitBreakerRegistry._registry
        assert "provider-b" in CircuitBreakerRegistry._registry

    def test_reset_all(self) -> None:
        """reset() without name clears all breakers."""
        CircuitBreakerRegistry.get("provider-a")
        CircuitBreakerRegistry.get("provider-b")
        CircuitBreakerRegistry.reset()
        assert len(CircuitBreakerRegistry._registry) == 0

    def test_all_states_returns_state_dict(self) -> None:
        """all_states() returns a dict of name -> state value."""
        CircuitBreakerRegistry.get("provider-a")
        CircuitBreakerRegistry.get("provider-b")
        states = CircuitBreakerRegistry.all_states()
        assert states == {"provider-a": "closed", "provider-b": "closed"}


# ---------------------------------------------------------------------------
# calculate_backoff
# ---------------------------------------------------------------------------

class TestCalculateBackoff:
    """Tests for the calculate_backoff function."""

    def test_first_attempt_base_delay(self) -> None:
        """First attempt returns base_delay (with jitter)."""
        delay = calculate_backoff(attempt=1, base_delay=1.0, max_delay=60.0, jitter=False)
        assert delay == 1.0

    def test_exponential_growth(self) -> None:
        """Delay grows exponentially with attempts."""
        d1 = calculate_backoff(attempt=1, base_delay=1.0, max_delay=60.0, jitter=False)
        d2 = calculate_backoff(attempt=2, base_delay=1.0, max_delay=60.0, jitter=False)
        d3 = calculate_backoff(attempt=3, base_delay=1.0, max_delay=60.0, jitter=False)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0

    def test_max_delay_cap(self) -> None:
        """Delay is capped at max_delay."""
        delay = calculate_backoff(attempt=100, base_delay=1.0, max_delay=10.0, jitter=False)
        assert delay == 10.0

    def test_jitter_adds_randomness(self) -> None:
        """With jitter enabled, delay includes a random component."""
        # Run multiple times to verify jitter is applied
        delays = [calculate_backoff(attempt=1, base_delay=1.0, max_delay=60.0, jitter=True) for _ in range(20)]
        # At least some should differ from the base delay
        assert any(d != 1.0 for d in delays)


# ---------------------------------------------------------------------------
# retry_with_backoff
# ---------------------------------------------------------------------------

class TestRetryWithBackoff:
    """Tests for the retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        """Returns result immediately when function succeeds."""
        async def fn() -> str:
            return "success"

        result = await retry_with_backoff(fn, max_retries=3, base_delay=0.01, max_delay=0.1)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_success_after_retries(self) -> None:
        """Succeeds after a few failures."""
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("temporary failure")
            return "eventual-success"

        result = await retry_with_backoff(fn, max_retries=3, base_delay=0.01, max_delay=0.1)
        assert result == "eventual-success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_failure_after_all_retries(self) -> None:
        """Raises the last error after exhausting retries."""
        async def fn() -> str:
            raise RuntimeError("persistent failure")

        with pytest.raises(RuntimeError, match="persistent failure"):
            await retry_with_backoff(fn, max_retries=2, base_delay=0.01, max_delay=0.1)

    @pytest.mark.asyncio
    async def test_circuit_open_raises_immediately(self) -> None:
        """Raises CircuitOpenError when circuit breaker is open."""
        cb = CircuitBreaker("test", failure_threshold=1, success_threshold=2, recovery_timeout_seconds=30)
        await cb.record_failure()  # Open the circuit

        async def fn() -> str:
            return "should-not-reach"

        with pytest.raises(CircuitOpenError, match="Circuit open for test"):
            await retry_with_backoff(fn, max_retries=3, base_delay=0.01, max_delay=0.1, circuit_breaker=cb)

    @pytest.mark.asyncio
    async def test_no_circuit_breaker_works(self) -> None:
        """retry_with_backoff works without a circuit breaker."""
        async def fn() -> str:
            return "ok"

        result = await retry_with_backoff(fn, max_retries=3, base_delay=0.01, max_delay=0.1)
        assert result == "ok"


# ---------------------------------------------------------------------------
# call_with_timeout
# ---------------------------------------------------------------------------

class TestCallWithTimeout:
    """Tests for the call_with_timeout function."""

    @pytest.mark.asyncio
    async def test_returns_result_within_timeout(self) -> None:
        """Returns the function result when it completes within the timeout."""
        async def fn() -> str:
            return "quick-result"

        result = await call_with_timeout(fn, timeout_seconds=5, provider_name="test-provider")
        assert result == "quick-result"

    @pytest.mark.asyncio
    async def test_raises_llm_timeout_error_on_timeout(self) -> None:
        """Raises LLMTimeoutError when the function exceeds the timeout."""
        async def fn() -> str:
            await asyncio.sleep(10)
            return "too-late"

        with pytest.raises(LLMTimeoutError, match="Timed out while calling provider 'test-provider'"):
            await call_with_timeout(fn, timeout_seconds=0.01, provider_name="test-provider")

    @pytest.mark.asyncio
    async def test_propagates_exception(self) -> None:
        """Exceptions from the function are propagated."""
        async def fn() -> str:
            raise ValueError("something went wrong")

        with pytest.raises(ValueError, match="something went wrong"):
            await call_with_timeout(fn, timeout_seconds=5, provider_name="test-provider")
