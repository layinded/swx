# pyright: reportAttributeAccessIssue=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAny=false

import importlib
import sys
import types
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from swx_core.events import event_bus
from swx_core.models.llm_provider_config import LLMProviderConfigCreate, LLMProviderConfigUpdate


def config(name: str, provider: str = "openai"):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {"id": uuid.uuid4(), "provider": provider, "name": name, "model_name": "gpt-4o", "credentials": {"api_key": "secret"}, "default_params": {}, "priority": 0, "is_primary": name == "primary", "is_active": True, "supported_phases": ["chat"], "cost_per_1k_tokens": 0.01, "supports_streaming": True, "supports_json_mode": True, "timeout_seconds": 5, "max_retries": 1, "circuit_breaker_threshold": 2, "circuit_breaker_reset_seconds": 10, "rate_limit_per_minute": None, "daily_token_limit": None, "extra_data": {}, "created_at": now, "updated_at": now}
    return SimpleNamespace(**data, model_dump=lambda: data)


def import_llm_module(module_name: str):
    class LLMRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    providers_module = types.ModuleType("swx_core.services.llm.providers")
    providers_module.BaseLLMProvider = object
    providers_module.LLMRequest = LLMRequest
    fake_modules = {
        "swx_core.services.llm.providers": providers_module,
        "swx_core.services.llm.providers.openai_provider": types.SimpleNamespace(OpenAIProvider=object),
        "swx_core.services.llm.providers.azure_provider": types.SimpleNamespace(AzureProvider=object),
        "swx_core.services.llm.providers.ollama_provider": types.SimpleNamespace(OllamaProvider=object),
        "swx_core.services.llm.providers.anthropic_provider": types.SimpleNamespace(AnthropicProvider=object),
    }
    sys.modules.pop(module_name, None)
    if module_name.endswith("llm_service"):
        sys.modules.pop("swx_core.services.llm.provider_factory", None)
    with patch.dict(sys.modules, fake_modules):
        return importlib.import_module(module_name)


class TestLLMEvents:
    async def test_generate_success_and_provider_failure_with_fallback(self):
        llm_service = import_llm_module("swx_core.services.llm.llm_service")

        session = AsyncMock()
        primary_provider = MagicMock()
        primary_provider.generate = AsyncMock(side_effect=RuntimeError("boom"))
        fallback_provider = MagicMock()
        fallback_provider.generate = AsyncMock(return_value=SimpleNamespace(success=True, error=None, provider="openai", model="gpt-4o", tokens_used=20, prompt_tokens=8, completion_tokens=12, latency_ms=5, content='{"answer":"ok"}'))

        with patch.object(llm_service, "get_provider_chain", new_callable=AsyncMock, return_value=[(primary_provider, config("primary")), (fallback_provider, config("fallback", provider="anthropic"))]):
            with patch.object(llm_service, "retry_with_backoff", new_callable=AsyncMock, side_effect=[RuntimeError("boom"), SimpleNamespace(success=True, error=None, provider="openai", model="gpt-4o", tokens_used=20, prompt_tokens=8, completion_tokens=12, latency_ms=5, content='{"answer":"ok"}')]):
                with patch.object(llm_service, "call_with_timeout", new_callable=AsyncMock):
                    with patch.object(llm_service, "_log_usage", new_callable=AsyncMock):
                        with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                            result = await llm_service.generate(session, "Hello", json_mode=True, account_id=uuid.uuid4())

        assert result["answer"] == "ok"
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["llm.provider_failed", "llm.generate"]

    async def test_provider_config_crud_clears_cache(self):
        llm_service = import_llm_module("swx_core.services.llm.llm_service")

        session = AsyncMock()
        create_data = LLMProviderConfigCreate(provider="openai", name="cfg", model_name="gpt-4o", credentials={"api_key": "secret"})
        update_data = LLMProviderConfigUpdate(name="cfg-2")
        stored = config("cfg")

        with patch.object(llm_service, "llm_provider_repository") as mock_repo:
            mock_repo.create = AsyncMock(return_value=stored)
            mock_repo.update = AsyncMock(return_value=stored)
            mock_repo.delete = AsyncMock(return_value=True)
            with patch.object(llm_service, "clear_provider_cache") as mock_clear:
                created = await llm_service.create_provider_config(session, create_data)
                updated = await llm_service.update_provider_config(session, uuid.uuid4(), update_data)
                deleted = await llm_service.delete_provider_config(session, uuid.uuid4())

        assert created.name == "cfg"
        assert updated.name == "cfg"
        assert deleted == {"deleted": True}
        assert mock_clear.call_count == 3

    async def test_provider_chain_cache_ttl_behavior(self):
        provider_factory = import_llm_module("swx_core.services.llm.provider_factory")

        session = AsyncMock()
        primary = config("primary")
        fallback = config("fallback", provider="anthropic")
        provider_factory.clear_cache()
        with patch.object(provider_factory.llm_provider_repository, "get_primary_for_phase", new_callable=AsyncMock, return_value=primary) as mock_primary:
            with patch.object(provider_factory.llm_provider_repository, "get_fallbacks_for_phase", new_callable=AsyncMock, return_value=[fallback]) as mock_fallbacks:
                with patch.object(provider_factory, "create_provider", side_effect=[MagicMock(), MagicMock(), MagicMock(), MagicMock()]):
                    with patch.object(provider_factory.time, "monotonic", side_effect=[0.0, 0.0, 30.0, 61.0, 61.0]):
                        first = await provider_factory.get_provider_chain(session, "chat")
                        second = await provider_factory.get_provider_chain(session, "chat")
                        third = await provider_factory.get_provider_chain(session, "chat")

        assert len(first) == len(second) == len(third) == 2
        assert mock_primary.await_count == 2
        assert mock_fallbacks.await_count == 2
