from abc import ABC

from swx_core.contracts.llm import LLMProviderContract, LLMRequest, LLMResponse, SSEEvent, ValidateProviderResult


class BaseLLMProvider(LLMProviderContract, ABC):
    """Common base type for concrete LLM provider adapters."""


__all__ = ["BaseLLMProvider", "LLMRequest", "LLMResponse", "SSEEvent", "ValidateProviderResult"]
