"""LLM request/response contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Literal


SSEEventType = Literal["text_delta", "usage", "error", "done"]


@dataclass(frozen=True)
class SSEEvent:
    """Structured Server-Sent Event for LLM streaming.

    Every event produced by ``stream()`` is an SSEEvent.  Consumers
    inspect ``event_type`` to decide how to handle the payload:

    - ``text_delta`` – one chunk of completion text (``data`` holds the string)
    - ``usage``       – token usage stats (``data`` holds ``UsagePayload``)
    - ``error``       – mid-stream error (``data`` holds ``ErrorPayload``)
    - ``done``        – terminal event, no payload
    """

    event_type: SSEEventType
    data: str | dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 1.0
    json_mode: bool = False
    stop_sequences: list[str] | None = None


@dataclass
class LLMResponse:
    success: bool
    content: str
    structured_output: dict[str, Any] | None = None
    error: str | None = None
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class ValidateProviderResult:
    """Result of validating a provider's API key and listing available models."""
    valid: bool
    models: list[str] = field(default_factory=list)
    error: str | None = None


class LLMProviderContract(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncGenerator[SSEEvent, None]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    async def validate_api_key(self) -> ValidateProviderResult:
        """Validate that the configured API key works with this provider.

        Returns a result indicating validity, available models, and any error.
        Default implementation delegates to health_check().
        """
        try:
            is_healthy = await self.health_check()
            if is_healthy:
                return ValidateProviderResult(valid=True)
            return ValidateProviderResult(valid=False, error="Health check failed")
        except Exception as exc:
            return ValidateProviderResult(valid=False, error=str(exc))

    async def list_models(self) -> list[str]:
        """List available models for this provider.

        Returns model IDs. Default implementation returns an empty list
        since not all providers expose a model listing API.
        """
        return []
