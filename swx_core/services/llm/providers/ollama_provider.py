import logging
from json import JSONDecodeError
from json import loads
from time import monotonic
from typing import Any, AsyncGenerator

import httpx

from swx_core.contracts.llm import LLMRequest, LLMResponse, SSEEvent, ValidateProviderResult
from swx_core.services.llm.providers import BaseLLMProvider


logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str, api_key: str | None, provider_config: dict[str, Any] | None = None):
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60)
        self.config = provider_config or {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started_at = monotonic()
        model_name = self.config.get("model_name", "llama3.2")
        try:
            messages = _messages(request)
            response = await self.client.post(
                "/api/chat",
                json={
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": request.temperature, "num_predict": request.max_tokens, "top_p": request.top_p},
                },
            )
            response.raise_for_status()
            payload = response.json()
            prompt_tokens = int(payload.get("prompt_eval_count", 0))
            completion_tokens = int(payload.get("eval_count", 0))
            return LLMResponse(
                True,
                payload.get("message", {}).get("content", ""),
                model=model_name,
                provider="ollama",
                tokens_used=prompt_tokens + completion_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=int((monotonic() - started_at) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM provider %s failed: %s", self.__class__.__name__, exc)
            return LLMResponse(False, "", error=str(exc), model=model_name, provider="ollama", latency_ms=int((monotonic() - started_at) * 1000))

    async def stream(self, request: LLMRequest) -> AsyncGenerator[SSEEvent, None]:
        model_name = self.config.get("model_name", "llama3.2")
        messages = _messages(request)
        try:
            async with self.client.stream("POST", "/api/chat", json={"model": model_name, "messages": messages, "stream": True, "options": {"temperature": request.temperature, "num_predict": request.max_tokens, "top_p": request.top_p}}) as response:
                response.raise_for_status()
                prompt_tokens = 0
                completion_tokens = 0
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        payload = loads(line)
                    except JSONDecodeError:
                        continue
                    content = payload.get("message", {}).get("content")
                    if content:
                        yield SSEEvent(event_type="text_delta", data=str(content))
                    if payload.get("done", False):
                        prompt_tokens = int(payload.get("prompt_eval_count", 0))
                        completion_tokens = int(payload.get("eval_count", 0))
            if prompt_tokens or completion_tokens:
                yield SSEEvent(event_type="usage", data={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens})
            yield SSEEvent(event_type="done")
        except Exception as exc:
            yield SSEEvent(event_type="error", data={"code": "STREAM_ERROR", "message": str(exc)})
            raise

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("/api/tags")
            return response.is_success
        except Exception:
            return False

    async def validate_api_key(self) -> ValidateProviderResult:
        try:
            response = await self.client.get("/api/tags")
            if response.is_success:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return ValidateProviderResult(valid=True, models=models)
            return ValidateProviderResult(valid=False, error=f"Ollama returned status {response.status_code}")
        except Exception as exc:
            return ValidateProviderResult(valid=False, error=str(exc))

    async def list_models(self) -> list[str]:
        try:
            response = await self.client.get("/api/tags")
            if response.is_success:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
            from swx_core.config.settings import settings
            return list(settings.LLM_DEFAULT_MODELS_OLLAMA)
        except Exception:
            from swx_core.config.settings import settings
            return list(settings.LLM_DEFAULT_MODELS_OLLAMA)


def _messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages
