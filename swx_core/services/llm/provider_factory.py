import time

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.llm_provider_config import LLMProviderConfig, LLMProviderType
from swx_core.repositories import llm_provider_repository
from swx_core.services.llm.config_resolver import resolve_api_key, resolve_config
from swx_core.services.llm.providers import BaseLLMProvider
from swx_core.services.llm.providers.anthropic_provider import AnthropicProvider
from swx_core.services.llm.providers.azure_provider import AzureProvider
from swx_core.services.llm.providers.ollama_provider import OllamaProvider
from swx_core.services.llm.providers.openai_provider import OpenAIProvider

_provider_cache: dict[str, BaseLLMProvider] = {}
_chain_cache: dict[str, tuple[list[tuple[BaseLLMProvider, LLMProviderConfig]], float]] = {}
_CHAIN_TTL: float = 60.0


def resolve_credentials(config: LLMProviderConfig) -> dict[str, object]:
    resolved = resolve_config(config.credentials)
    if config.credential_source == "encrypted_db" and config.encrypted_api_key:
        resolved["api_key"] = resolve_api_key(
            config.credentials, config.credential_source, config.encrypted_api_key
        )
    return resolved


def _get_cache_key(config: LLMProviderConfig) -> str:
    return f"{config.provider}:{config.model_name}:{','.join(sorted(config.credentials.keys()))}"


def clear_cache() -> None:
    _provider_cache.clear()
    _chain_cache.clear()


def create_provider(config: LLMProviderConfig) -> BaseLLMProvider | None:
    cache_key = _get_cache_key(config)
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]
    credentials = resolve_credentials(config)
    provider_config = {"model_name": config.model_name, **config.default_params}
    provider_type = LLMProviderType(config.provider)
    provider: BaseLLMProvider | None = None
    if provider_type == LLMProviderType.OPENAI:
        provider = OpenAIProvider(
            str(credentials.get("api_key", "")),
            str(credentials.get("organization", "")),
            str(credentials.get("base_url", "")),
            provider_config,
        )
    elif provider_type == LLMProviderType.AZURE:
        provider_config["deployment"] = str(credentials.get("deployment", config.model_name))
        provider = AzureProvider(
            str(credentials.get("api_key", "")),
            str(credentials.get("endpoint", "")),
            str(credentials.get("deployment", config.model_name)),
            provider_config,
        )
    elif provider_type == LLMProviderType.OLLAMA:
        provider = OllamaProvider(str(credentials.get("base_url", "http://localhost:11434")), str(credentials.get("api_key", "")) or None, provider_config)
    elif provider_type == LLMProviderType.ANTHROPIC:
        provider = AnthropicProvider(str(credentials.get("api_key", "")), provider_config)
    if provider is not None:
        _provider_cache[cache_key] = provider
    return provider


async def get_provider_chain(session: AsyncSession, phase: str) -> list[tuple[BaseLLMProvider, LLMProviderConfig]]:
    now = time.monotonic()
    cached = _chain_cache.get(phase)
    if cached is not None and now - cached[1] < _CHAIN_TTL:
        return cached[0]
    chain: list[tuple[BaseLLMProvider, LLMProviderConfig]] = []
    primary = await llm_provider_repository.get_primary_for_phase(session, phase)
    if primary is not None:
        try:
            provider = create_provider(primary)
        except Exception:
            provider = None
        if provider is not None:
            chain.append((provider, primary))
    for config in await llm_provider_repository.get_fallbacks_for_phase(session, phase, primary.id if primary else None):
        try:
            provider = create_provider(config)
            if provider is not None:
                chain.append((provider, config))
        except Exception:
            continue
    if not chain:
        raise ValueError(f"No available LLM providers configured for phase '{phase}'")
    _chain_cache[phase] = (chain, time.monotonic())
    return chain
