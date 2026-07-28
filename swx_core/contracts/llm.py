"""LLM request/response contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator


@dataclass
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


class LLMProviderContract(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
