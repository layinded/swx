# pyright: reportMissingImports=false

import logging
from time import monotonic
from typing import Any, AsyncGenerator

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore[assignment]

from swx_core.contracts.llm import LLMRequest, LLMResponse
from swx_core.services.llm.providers import BaseLLMProvider


logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, provider_config: dict[str, Any] | None = None):
        if AsyncAnthropic is None:
            raise RuntimeError("anthropic package is not installed")
        self.client = AsyncAnthropic(api_key=api_key)
        self.config = provider_config or {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started_at = monotonic()
        model_name = self.config.get("model_name", "claude-3-5-sonnet-latest")
        try:
            system_prompt = _system_prompt(request)
            messages = [{"role": "user", "content": request.prompt}]
            response = await self.client.messages.create(
                model=model_name,
                system=system_prompt or None,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                stop_sequences=request.stop_sequences,
            )
            text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            usage = response.usage
            return LLMResponse(
                True,
                "".join(text_parts),
                model=str(response.model),
                provider="anthropic",
                tokens_used=int(usage.input_tokens + usage.output_tokens),
                prompt_tokens=int(usage.input_tokens),
                completion_tokens=int(usage.output_tokens),
                latency_ms=int((monotonic() - started_at) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM provider %s failed: %s", self.__class__.__name__, exc)
            return LLMResponse(False, "", error=str(exc), model=model_name, provider="anthropic", latency_ms=int((monotonic() - started_at) * 1000))

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        model_name = self.config.get("model_name", "claude-3-5-sonnet-latest")
        messages = [{"role": "user", "content": request.prompt}]
        async with self.client.messages.stream(model=model_name, system=_system_prompt(request) or None, messages=messages, temperature=request.temperature, max_tokens=request.max_tokens, top_p=request.top_p) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            await self.client.messages.create(model=self.config.get("model_name", "claude-3-5-sonnet-latest"), max_tokens=1, messages=[{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False


def _system_prompt(request: LLMRequest) -> str | None:
    if request.json_mode:
        suffix = "Respond with a valid JSON object only."
        return f"{request.system_prompt}\n\n{suffix}" if request.system_prompt else suffix
    return request.system_prompt
