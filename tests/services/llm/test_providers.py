# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for LLM provider adapters — validate_api_key() and list_models() contracts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from swx_core.contracts.llm import LLMRequest, LLMResponse, SSEEvent, ValidateProviderResult


class TestValidateProviderResult:
    """Tests for the ValidateProviderResult dataclass."""

    def test_valid_result_with_models(self) -> None:
        result = ValidateProviderResult(valid=True, models=["gpt-4o", "gpt-4o-mini"])
        assert result.valid is True
        assert len(result.models) == 2
        assert result.error is None

    def test_invalid_result_with_error(self) -> None:
        result = ValidateProviderResult(valid=False, error="Invalid API key")
        assert result.valid is False
        assert result.models == []
        assert result.error == "Invalid API key"

    def test_default_values(self) -> None:
        result = ValidateProviderResult(valid=True)
        assert result.models == []
        assert result.error is None


class TestSSEEvent:
    """Tests for the SSEEvent dataclass."""

    def test_text_delta_event(self) -> None:
        event = SSEEvent(event_type="text_delta", data="Hello, ")
        assert event.event_type == "text_delta"
        assert event.data == "Hello, "

    def test_usage_event(self) -> None:
        event = SSEEvent(event_type="usage", data={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
        assert event.event_type == "usage"
        assert isinstance(event.data, dict)
        assert event.data["total_tokens"] == 30

    def test_error_event(self) -> None:
        event = SSEEvent(event_type="error", data={"code": "STREAM_ERROR", "message": "timeout"})
        assert event.event_type == "error"
        assert isinstance(event.data, dict)

    def test_done_event(self) -> None:
        event = SSEEvent(event_type="done")
        assert event.event_type == "done"
        assert event.data is None

    def test_frozen(self) -> None:
        event = SSEEvent(event_type="text_delta", data="hi")
        with pytest.raises(AttributeError):
            event.event_type = "usage"  # type: ignore[misc]


class TestLLMProviderContractDefaultValidate:
    """Tests for the default validate_api_key() and list_models() on BaseLLMProvider."""

    @pytest.mark.asyncio
    async def test_default_validate_healthy(self) -> None:
        """When health_check succeeds, validate_api_key returns valid=True."""
        from swx_core.services.llm.providers import BaseLLMProvider

        class HealthyProvider(BaseLLMProvider):
            async def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(success=True, content="ok")

            def stream(self, request: LLMRequest):
                async def _gen():
                    yield SSEEvent(event_type="done")
                return _gen()

            async def health_check(self) -> bool:
                return True

        provider = HealthyProvider()
        result = await provider.validate_api_key()
        assert result.valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_default_validate_unhealthy(self) -> None:
        """When health_check fails, validate_api_key returns valid=False."""
        from swx_core.services.llm.providers import BaseLLMProvider

        class UnhealthyProvider(BaseLLMProvider):
            async def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(success=False, content="", error="unhealthy")

            def stream(self, request: LLMRequest):
                async def _gen():
                    yield SSEEvent(event_type="done")
                return _gen()

            async def health_check(self) -> bool:
                return False

        provider = UnhealthyProvider()
        result = await provider.validate_api_key()
        assert result.valid is False
        assert "Health check failed" in result.error

    @pytest.mark.asyncio
    async def test_default_validate_exception(self) -> None:
        """When health_check raises, validate_api_key returns valid=False with error."""
        from swx_core.services.llm.providers import BaseLLMProvider

        class ErrorProvider(BaseLLMProvider):
            async def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(success=False, content="", error="error")

            def stream(self, request: LLMRequest):
                async def _gen():
                    yield SSEEvent(event_type="done")
                return _gen()

            async def health_check(self) -> bool:
                raise RuntimeError("Connection refused")

        provider = ErrorProvider()
        result = await provider.validate_api_key()
        assert result.valid is False
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_default_list_models_returns_empty(self) -> None:
        """BaseLLMProvider.list_models() returns an empty list by default."""
        from swx_core.services.llm.providers import BaseLLMProvider

        class MinimalProvider(BaseLLMProvider):
            async def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(success=True, content="ok")

            def stream(self, request: LLMRequest):
                async def _gen():
                    yield SSEEvent(event_type="done")
                return _gen()

            async def health_check(self) -> bool:
                return True

        provider = MinimalProvider()
        models = await provider.list_models()
        assert models == []


class TestOpenAIProviderValidation:
    """Tests for OpenAI provider validate_api_key() and list_models()."""

    @pytest.mark.asyncio
    async def test_validate_success(self) -> None:
        """validate_api_key returns valid=True when models.list() succeeds."""
        from swx_core.services.llm.providers.openai_provider import OpenAIProvider

        mock_models = [MagicMock(id="gpt-4o"), MagicMock(id="gpt-4o-mini")]
        mock_page = MagicMock()
        mock_page.data = mock_models

        with patch("swx_core.services.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(return_value=mock_page)

            provider = OpenAIProvider(api_key="sk-test", organization=None, base_url=None)
            result = await provider.validate_api_key()

        assert result.valid is True
        assert "gpt-4o" in result.models
        assert "gpt-4o-mini" in result.models

    @pytest.mark.asyncio
    async def test_validate_failure(self) -> None:
        """validate_api_key returns valid=False when models.list() raises."""
        from swx_core.services.llm.providers.openai_provider import OpenAIProvider

        with patch("swx_core.services.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(side_effect=RuntimeError("Invalid API key"))

            provider = OpenAIProvider(api_key="sk-bad", organization=None, base_url=None)
            result = await provider.validate_api_key()

        assert result.valid is False
        assert "Invalid API key" in result.error

    @pytest.mark.asyncio
    async def test_list_models_success(self) -> None:
        """list_models returns sorted model IDs on success."""
        from swx_core.services.llm.providers.openai_provider import OpenAIProvider

        mock_models = [MagicMock(id="gpt-4o-mini"), MagicMock(id="gpt-4o")]
        mock_page = MagicMock()
        mock_page.data = mock_models

        with patch("swx_core.services.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(return_value=mock_page)

            provider = OpenAIProvider(api_key="sk-test", organization=None, base_url=None)
            models = await provider.list_models()

        assert models == ["gpt-4o", "gpt-4o-mini"]

    @pytest.mark.asyncio
    async def test_list_models_fallback_on_error(self) -> None:
        """list_models falls back to settings defaults when the API call fails."""
        from swx_core.services.llm.providers.openai_provider import OpenAIProvider

        with patch("swx_core.services.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(side_effect=RuntimeError("Network error"))

            provider = OpenAIProvider(api_key="sk-test", organization=None, base_url=None)
            models = await provider.list_models()

        # Should return settings.LLM_DEFAULT_MODELS_OPENAI
        assert isinstance(models, list)
        assert len(models) > 0


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_defaults(self) -> None:
        req = LLMRequest(prompt="Hello")
        assert req.prompt == "Hello"
        assert req.system_prompt is None
        assert req.temperature == 0.7
        assert req.max_tokens == 1024
        assert req.top_p == 1.0
        assert req.json_mode is False
        assert req.stop_sequences is None

    def test_custom_values(self) -> None:
        req = LLMRequest(
            prompt="Test",
            system_prompt="You are helpful",
            temperature=0.5,
            max_tokens=512,
            top_p=0.9,
            json_mode=True,
            stop_sequences=["\n"],
        )
        assert req.temperature == 0.5
        assert req.json_mode is True