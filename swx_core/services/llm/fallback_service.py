"""Fallback Chain Service
------------------------
Try LLM providers in priority order with circuit-breaker integration.

On each call the chain iterates providers by priority:
- 5xx / timeout / ``CircuitOpenError`` → try next provider
- 4xx client error → stop immediately (the request is bad, not the provider)
- Success → return result

The chain composes with ``CircuitBreaker`` from ``resilience.py`` so that
a permanently-broken provider is skipped after its failure threshold.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from swx_core.contracts.llm import LLMRequest, LLMResponse, SSEEvent
from swx_core.services.llm.provider_factory import get_provider_chain
from swx_core.services.llm.resilience import CircuitBreakerRegistry, CircuitOpenError, LLMTimeoutError

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_AttemptEntry = dict[str, str | bool | None]


@dataclass
class FallbackResult:
    """Outcome of a fallback chain invocation."""

    success: bool
    response: LLMResponse | None = None
    stream: AsyncGenerator[SSEEvent, None] | None = None
    provider_used: str | None = None
    model_used: str | None = None
    attempts: list[_AttemptEntry] = field(default_factory=list)
    error: str | None = None


def _is_client_error(exc: Exception) -> bool:
    """Return True for 4xx-style errors that should stop the chain."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and 400 <= status < 500:
        return True
    return False


class FallbackChain:
    """Execute an LLM request across a provider chain with fallback.

    Usage::

        chain = FallbackChain()
        result = await chain.generate(session, request, phase="chat")
        if result.success:
            print(result.response.content)
    """

    max_attempts: int

    def __init__(self, max_attempts: int = 5) -> None:
        self.max_attempts = max_attempts

    async def generate(
        self,
        session: AsyncSession,
        request: LLMRequest,
        phase: str = "default",
    ) -> FallbackResult:
        """Try each provider in priority order until one succeeds or all fail.

        Args:
            session: Database session for provider lookups.
            request: The LLM request to send.
            phase: Provider phase (e.g. "chat", "embedding").

        Returns:
            FallbackResult with the successful response or final error.
        """
        try:
            provider_chain = await get_provider_chain(session, phase)
        except ValueError as exc:
            return FallbackResult(success=False, error=str(exc))

        attempts: list[_AttemptEntry] = []
        for provider, config in provider_chain[: self.max_attempts]:
            failure_threshold = config.circuit_breaker_threshold or 5
            recovery_timeout = config.circuit_breaker_reset_seconds or 30
            breaker = CircuitBreakerRegistry.get(
                name=f"llm:{config.provider}",
                failure_threshold=failure_threshold,
                success_threshold=1,
                recovery_timeout_seconds=recovery_timeout,
            )

            if not await breaker.allow_request():
                attempts.append({"provider": config.provider, "model": config.model_name, "error": "circuit_open", "success": False})
                continue

            try:
                response = await provider.generate(request)
                await breaker.record_success()
                return FallbackResult(
                    success=True,
                    response=response,
                    provider_used=config.provider,
                    model_used=config.model_name,
                    attempts=attempts + [{"provider": config.provider, "model": config.model_name, "success": True}],
                )
            except CircuitOpenError:
                attempts.append({"provider": config.provider, "model": config.model_name, "error": "circuit_open", "success": False})
                continue
            except LLMTimeoutError as exc:
                await breaker.record_failure()
                attempts.append({"provider": config.provider, "model": config.model_name, "error": str(exc), "success": False})
                continue
            except Exception as exc:
                if _is_client_error(exc):
                    await breaker.record_success()
                    return FallbackResult(
                        success=False,
                        error=str(exc),
                        attempts=attempts + [{"provider": config.provider, "model": config.model_name, "error": str(exc), "success": False}],
                    )
                await breaker.record_failure()
                attempts.append({"provider": config.provider, "model": config.model_name, "error": str(exc), "success": False})
                continue

        last_error = attempts[-1]["error"] if attempts else "No providers available"
        return FallbackResult(success=False, error=str(last_error) if last_error else "No providers available", attempts=attempts)

    async def stream(
        self,
        session: AsyncSession,
        request: LLMRequest,
        phase: str = "default",
    ) -> AsyncGenerator[SSEEvent, None]:
        """Try each provider in priority order, yielding SSEEvents from the first success.

        Yields:
            SSEEvent objects from the successful provider.

        Raises:
            RuntimeError: If all providers fail.
        """
        try:
            provider_chain = await get_provider_chain(session, phase)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        last_exc: Exception | None = None
        all_circuits_open = True
        for provider, config in provider_chain[: self.max_attempts]:
            failure_threshold = config.circuit_breaker_threshold or 5
            recovery_timeout = config.circuit_breaker_reset_seconds or 30
            breaker = CircuitBreakerRegistry.get(
                name=f"llm:{config.provider}",
                failure_threshold=failure_threshold,
                success_threshold=1,
                recovery_timeout_seconds=recovery_timeout,
            )

            if not await breaker.allow_request():
                continue

            try:
                stream_gen = provider.stream(request)
                all_circuits_open = False
                first_event: SSEEvent | None = None
                async for event in stream_gen:
                    if first_event is None:
                        first_event = event
                        if event.event_type == "error":
                            await breaker.record_failure()
                            last_exc = RuntimeError(str(event.data))
                            first_event = None
                            break
                        await breaker.record_success()
                        yield event
                    else:
                        yield event

                if first_event is not None:
                    return

            except (CircuitOpenError, LLMTimeoutError) as exc:
                await breaker.record_failure()
                last_exc = exc
                continue
            except Exception as exc:
                if _is_client_error(exc):
                    await breaker.record_success()
                    raise
                await breaker.record_failure()
                last_exc = exc
                continue

        if all_circuits_open and last_exc is None:
            raise RuntimeError(f"All provider circuits are open for phase '{phase}' — try again later")
        raise RuntimeError(f"All providers failed for phase '{phase}'") from last_exc