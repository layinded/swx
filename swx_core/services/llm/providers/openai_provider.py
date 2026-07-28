# pyright: reportMissingImports=false

from time import monotonic
from typing import Any, AsyncGenerator

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore[assignment]

from swx_core.contracts.llm import LLMRequest, LLMResponse
from swx_core.services.llm.providers import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, organization: str | None, base_url: str | None, provider_config: dict[str, Any] | None = None):
        if AsyncOpenAI is None:
            raise RuntimeError("openai package is not installed")
        self.client = AsyncOpenAI(api_key=api_key, organization=organization or None, base_url=base_url or None)
        self.config = provider_config or {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started = monotonic()
        model_name = self.config.get("model_name", "gpt-4o")
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=_messages(request),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                stop=request.stop_sequences,
                response_format={"type": "json_object"} if request.json_mode else None,
            )
            usage = response.usage
            return LLMResponse(
                True,
                response.choices[0].message.content or "",
                model=response.model,
                provider="openai",
                tokens_used=int(usage.total_tokens if usage else 0),
                prompt_tokens=int(usage.prompt_tokens if usage else 0),
                completion_tokens=int(usage.completion_tokens if usage else 0),
                latency_ms=int((monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return LLMResponse(False, "", error=str(exc), model=model_name, provider="openai", latency_ms=int((monotonic() - started) * 1000))

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        model_name = self.config.get("model_name", "gpt-4o")
        async with self.client.chat.completions.stream(model=model_name, messages=_messages(request), temperature=request.temperature, max_tokens=request.max_tokens, top_p=request.top_p) as stream:
            async for event in stream:
                if event.type == "content.delta" and getattr(event, "delta", None):
                    yield str(event.delta)

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


def _messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages
