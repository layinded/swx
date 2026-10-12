# pyright: reportAttributeAccessIssue=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAny=false

"""Tests for the FallbackChain service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from swx_core.contracts.llm import LLMRequest, LLMResponse, SSEEvent
from swx_core.services.llm.fallback_service import FallbackChain, FallbackResult, _is_client_error
from swx_core.services.llm.resilience import CircuitOpenError


class TestIsClientError:
    def test_4xx_is_client_error(self):
        exc = Exception("test")
        exc.status_code = 403  # type: ignore[attr-defined]
        assert _is_client_error(exc) is True

    def test_400_is_client_error(self):
        exc = Exception("test")
        exc.status_code = 400  # type: ignore[attr-defined]
        assert _is_client_error(exc) is True

    def test_499_is_client_error(self):
        exc = Exception("test")
        exc.status_code = 499  # type: ignore[attr-defined]
        assert _is_client_error(exc) is True

    def test_5xx_is_not_client_error(self):
        exc = Exception("test")
        exc.status_code = 500  # type: ignore[attr-defined]
        assert _is_client_error(exc) is False

    def test_no_status_code_is_not_client_error(self):
        assert _is_client_error(Exception("test")) is False


class TestFallbackChainGenerate:
    @pytest.mark.asyncio
    async def test_no_providers_returns_error(self):
        """When get_provider_chain raises ValueError, return error result."""
        chain = FallbackChain()
        session = AsyncMock()

        with patch("swx_core.services.llm.fallback_service.get_provider_chain", side_effect=ValueError("No providers")):
            result = await chain.generate(session, LLMRequest(prompt="hi"), phase="chat")

        assert result.success is False
        assert result.error == "No providers"
        assert result.response is None

    @pytest.mark.asyncio
    async def test_first_provider_succeeds(self):
        """When the first provider succeeds, return its response immediately."""
        chain = FallbackChain()
        session = AsyncMock()
        mock_provider = AsyncMock()
        expected_response = LLMResponse(success=True, content="hello", model="gpt-4o", provider="openai")
        mock_provider.generate = AsyncMock(return_value=expected_response)
        mock_config = MagicMock(
            provider="openai",
            model_name="gpt-4o",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        with patch("swx_core.services.llm.fallback_service.get_provider_chain", return_value=[(mock_provider, mock_config)]):
            with patch("swx_core.services.llm.fallback_service.CircuitBreakerRegistry") as mock_registry:
                mock_breaker = AsyncMock()
                mock_breaker.allow_request = AsyncMock(return_value=True)
                mock_registry.get.return_value = mock_breaker

                result = await chain.generate(session, LLMRequest(prompt="hi"), phase="chat")

        assert result.success is True
        assert result.response is expected_response
        assert result.provider_used == "openai"

    @pytest.mark.asyncio
    async def test_fallback_on_server_error(self):
        """When first provider fails with server error, try next provider."""
        chain = FallbackChain()
        session = AsyncMock()

        fail_provider = AsyncMock()
        fail_provider.generate = AsyncMock(side_effect=Exception("Server error"))
        fail_config = MagicMock(
            provider="openai",
            model_name="gpt-4o",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        success_provider = AsyncMock()
        success_response = LLMResponse(success=True, content="hello", model="claude-3", provider="anthropic")
        success_provider.generate = AsyncMock(return_value=success_response)
        success_config = MagicMock(
            provider="anthropic",
            model_name="claude-3",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        with patch("swx_core.services.llm.fallback_service.get_provider_chain", return_value=[(fail_provider, fail_config), (success_provider, success_config)]):
            with patch("swx_core.services.llm.fallback_service.CircuitBreakerRegistry") as mock_registry:
                mock_breaker = AsyncMock()
                mock_breaker.allow_request = AsyncMock(return_value=True)
                mock_registry.get.return_value = mock_breaker

                result = await chain.generate(session, LLMRequest(prompt="hi"), phase="chat")

        assert result.success is True
        assert result.provider_used == "anthropic"

    @pytest.mark.asyncio
    async def test_client_error_stops_chain(self):
        """When a provider returns 4xx, stop the chain immediately."""
        chain = FallbackChain()
        session = AsyncMock()

        fail_provider = AsyncMock()
        client_error = Exception("Not Found")
        client_error.status_code = 404  # type: ignore[attr-defined]
        fail_provider.generate = AsyncMock(side_effect=client_error)
        fail_config = MagicMock(
            provider="openai",
            model_name="gpt-4o",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        success_provider = AsyncMock()
        success_response = LLMResponse(success=True, content="should not reach", model="claude-3", provider="anthropic")
        success_provider.generate = AsyncMock(return_value=success_response)
        success_config = MagicMock(
            provider="anthropic",
            model_name="claude-3",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        with patch("swx_core.services.llm.fallback_service.get_provider_chain", return_value=[(fail_provider, fail_config), (success_provider, success_config)]):
            with patch("swx_core.services.llm.fallback_service.CircuitBreakerRegistry") as mock_registry:
                mock_breaker = AsyncMock()
                mock_breaker.allow_request = AsyncMock(return_value=True)
                mock_registry.get.return_value = mock_breaker

                result = await chain.generate(session, LLMRequest(prompt="hi"), phase="chat")

        assert result.success is False
        assert "Not Found" in result.error

    @pytest.mark.asyncio
    async def test_circuit_open_skips_provider(self):
        """When circuit is open, skip that provider."""
        chain = FallbackChain()
        session = AsyncMock()

        blocked_provider = AsyncMock()
        blocked_config = MagicMock(
            provider="openai",
            model_name="gpt-4o",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        success_provider = AsyncMock()
        success_response = LLMResponse(success=True, content="hello", model="claude-3", provider="anthropic")
        success_provider.generate = AsyncMock(return_value=success_response)
        success_config = MagicMock(
            provider="anthropic",
            model_name="claude-3",
            circuit_breaker_threshold=5,
            circuit_breaker_reset_seconds=30,
        )

        with patch("swx_core.services.llm.fallback_service.get_provider_chain", return_value=[(blocked_provider, blocked_config), (success_provider, success_config)]):
            with patch("swx_core.services.llm.fallback_service.CircuitBreakerRegistry") as mock_registry:
                blocked_breaker = AsyncMock()
                blocked_breaker.allow_request = AsyncMock(return_value=False)
                success_breaker = AsyncMock()
                success_breaker.allow_request = AsyncMock(return_value=True)
                mock_registry.get.side_effect = [blocked_breaker, success_breaker]

                result = await chain.generate(session, LLMRequest(prompt="hi"), phase="chat")

        assert result.success is True
        assert result.provider_used == "anthropic"


class TestFallbackResult:
    def test_defaults(self):
        result = FallbackResult(success=False)
        assert result.success is False
        assert result.response is None
        assert result.stream is None
        assert result.provider_used is None
        assert result.model_used is None
        assert result.attempts == []
        assert result.error is None

    def test_with_values(self):
        result = FallbackResult(
            success=True,
            provider_used="openai",
            model_used="gpt-4o",
            error=None,
        )
        assert result.success is True
        assert result.provider_used == "openai"