# pyright: reportMissingImports=false

import logging
from time import monotonic
from typing import Any, AsyncGenerator

try:
    from openai import AsyncAzureOpenAI
except ImportError:
    AsyncAzureOpenAI = None  # type: ignore[assignment]

from swx_core.contracts.llm import LLMRequest, LLMResponse, SSEEvent, ValidateProviderResult
from swx_core.services.llm.providers import BaseLLMProvider


logger = logging.getLogger(__name__)


class AzureProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, endpoint: str | None, deployment: str | None, provider_config: dict[str, Any] | None = None):
        if AsyncAzureOpenAI is None:
            raise RuntimeError("openai package is not installed")
        self.client = AsyncAzureOpenAI(api_key=api_key, azure_endpoint=endpoint or "", azure_deployment=deployment or "", api_version="2024-02-01")
        self.config = provider_config or {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started_at = monotonic()
        model_name = self.config.get("deployment", self.config.get("model_name", "gpt-4o"))
        try:
            messages = _messages(request)
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                response_format={"type": "json_object"} if request.json_mode else None,
            )
            usage = response.usage
            return LLMResponse(
                True,
                response.choices[0].message.content or "",
                model=response.model,
                provider="azure",
                tokens_used=int(usage.total_tokens if usage else 0),
                prompt_tokens=int(usage.prompt_tokens if usage else 0),
                completion_tokens=int(usage.completion_tokens if usage else 0),
                latency_ms=int((monotonic() - started_at) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM provider %s failed: %s", self.__class__.__name__, exc)
            return LLMResponse(False, "", error=str(exc), model=model_name, provider="azure", latency_ms=int((monotonic() - started_at) * 1000))

    async def stream(self, request: LLMRequest) -> AsyncGenerator[SSEEvent, None]:
        model_name = self.config.get("deployment", self.config.get("model_name", "gpt-4o"))
        messages = _messages(request)
        try:
            async with self.client.chat.completions.stream(model=model_name, messages=messages, temperature=request.temperature, max_tokens=request.max_tokens, top_p=request.top_p) as stream:
                usage_snapshot = None
                async for event in stream:
                    if event.type == "content.delta" and getattr(event, "delta", None):
                        yield SSEEvent(event_type="text_delta", data=str(event.delta))
                    elif event.type == "message.done":
                        msg = event.message if hasattr(event, "message") else None
                        usage_obj = getattr(msg, "usage", None) if msg else None
                        if usage_obj:
                            usage_snapshot = usage_obj
            if usage_snapshot:
                yield SSEEvent(event_type="usage", data={"prompt_tokens": int(getattr(usage_snapshot, "prompt_tokens", 0)), "completion_tokens": int(getattr(usage_snapshot, "completion_tokens", 0)), "total_tokens": int(getattr(usage_snapshot, "total_tokens", 0))})
            yield SSEEvent(event_type="done")
        except Exception as exc:
            yield SSEEvent(event_type="error", data={"code": "STREAM_ERROR", "message": str(exc)})
            raise

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    async def validate_api_key(self) -> ValidateProviderResult:
        try:
            models_page = await self.client.models.list()
            model_ids = sorted(m.id for m in models_page.data)
            return ValidateProviderResult(valid=True, models=model_ids)
        except Exception as exc:
            return ValidateProviderResult(valid=False, error=str(exc))

    async def list_models(self) -> list[str]:
        try:
            models_page = await self.client.models.list()
            return sorted(m.id for m in models_page.data)
        except Exception:
            from swx_core.config.settings import settings
            return list(settings.LLM_DEFAULT_MODELS_AZURE)


def _messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages
