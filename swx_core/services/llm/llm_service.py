import json
import re
from time import monotonic
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events import event_bus
from swx_core.models.llm_provider_config import LLMProviderConfigCreate, LLMProviderConfigPublic, LLMProviderConfigUpdate, mask_credentials_map, CredentialSource
from swx_core.models.llm_usage_log import LLMUsageLogPublic
from swx_core.repositories import llm_provider_repository, llm_usage_repository
from swx_core.security.encryption import encrypt_value
from swx_core.services.llm.provider_factory import clear_cache as clear_provider_cache, create_provider, get_provider_chain
from swx_core.services.llm.providers import LLMRequest
from swx_core.services.llm.resilience import CircuitBreakerRegistry, call_with_timeout, retry_with_backoff
from swx_core.contracts.llm import SSEEvent, ValidateProviderResult


def _provider_public(config) -> LLMProviderConfigPublic:
    data = config.model_dump()
    data["credentials"] = mask_credentials_map(config.credentials)
    data["encrypted_api_key"] = None if not config.encrypted_api_key else "***"
    data["metadata"] = config.extra_data
    return LLMProviderConfigPublic.model_validate(data)


def _cost(rate: float | None, total_tokens: int) -> float:
    return round(((rate or 0.0) * total_tokens) / 1000, 6)


def _parse_response(content: str, json_mode: bool) -> dict[str, Any]:
    if not json_mode:
        return {"content": content}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        return json.loads(match.group(0)) if match else {"content": content, "parse_error": True}


async def _log_usage(session: AsyncSession, provider: str, model: str, phase: str | None, tokens: tuple[int, int, int], cost: float, latency: int, success: bool, error: str | None, account_id: UUID | None, provider_config_id: UUID | None = None) -> None:
    if not settings.LLM_USAGE_LOG_ENABLED:
        return
    await llm_usage_repository.create(
        session,
        {
            "provider_config_id": provider_config_id,
            "provider": provider,
            "model_name": model,
            "phase": phase,
            "prompt_tokens": tokens[0],
            "completion_tokens": tokens[1],
            "total_tokens": tokens[2],
            "cost_usd": cost,
            "latency_ms": latency,
            "success": success,
            "error_message": error,
            "account_id": account_id,
        },
    )


_CONFIG_FIELDS = ("provider", "name", "model_name", "credentials", "credential_source", "encrypted_api_key", "default_params", "priority", "is_primary", "is_active", "supported_phases", "cost_per_1k_tokens", "supports_streaming", "supports_json_mode", "timeout_seconds", "max_retries", "circuit_breaker_threshold", "circuit_breaker_reset_seconds", "rate_limit_per_minute", "daily_token_limit", "extra_data")


def _create_provider_payload(data: LLMProviderConfigCreate) -> llm_provider_repository.LLMProviderConfigData:
    return {field: getattr(data, field) for field in _CONFIG_FIELDS}  # pyright: ignore[reportReturnType]


def _update_provider_payload(data: LLMProviderConfigUpdate) -> llm_provider_repository.LLMProviderConfigData:
    return {field: getattr(data, field) for field in _CONFIG_FIELDS if getattr(data, field) is not None}  # pyright: ignore[reportReturnType]


def _resilience_config(config) -> tuple[int, int, int, int]:
    timeout = config.timeout_seconds if config.timeout_seconds is not None else settings.LLM_DEFAULT_TIMEOUT
    retries = config.max_retries if config.max_retries is not None else settings.LLM_MAX_RETRIES
    threshold = config.circuit_breaker_threshold if config.circuit_breaker_threshold is not None else settings.LLM_CIRCUIT_BREAKER_THRESHOLD
    reset = config.circuit_breaker_reset_seconds if config.circuit_breaker_reset_seconds is not None else settings.LLM_CIRCUIT_BREAKER_RESET_SECONDS
    return timeout, retries, threshold, reset


async def generate(session: AsyncSession, prompt: str, phase: str = "chat", system_prompt: str | None = None, json_mode: bool = False, account_id: UUID | None = None, **kwargs: Any) -> dict[str, Any]:
    request = LLMRequest(prompt=prompt, system_prompt=system_prompt, json_mode=json_mode, temperature=float(kwargs.get("temperature", 0.7)), max_tokens=int(kwargs.get("max_tokens", 1024)), top_p=float(kwargs.get("top_p", 1.0)), stop_sequences=kwargs.get("stop_sequences"))
    errors: list[str] = []
    for provider, config in await get_provider_chain(session, phase):
        timeout, retries, threshold, reset = _resilience_config(config)
        breaker = CircuitBreakerRegistry.get(f"{config.provider}:{config.id}", threshold, 1, reset)
        started = monotonic()
        try:
            response = await retry_with_backoff(lambda: call_with_timeout(lambda: provider.generate(request), timeout, config.name), retries, 0.5, 4.0, breaker)
            if not response.success:
                raise RuntimeError(response.error or f"{config.provider} failed")
            await breaker.record_success()
            cost = _cost(config.cost_per_1k_tokens, response.tokens_used)
            await _log_usage(session, response.provider, response.model or config.model_name, phase, (response.prompt_tokens, response.completion_tokens, response.tokens_used), cost, response.latency_ms or int((monotonic() - started) * 1000), True, None, account_id, config.id)
            parsed = _parse_response(response.content, json_mode)
            await event_bus.dispatch("llm.generate", payload={"provider": config.provider, "model": config.model_name, "phase": phase, "account_id": str(account_id) if account_id else None})
            return parsed
        except Exception as exc:  # noqa: BLE001
            await breaker.record_failure()
            errors.append(f"{config.provider}: {exc}")
            await event_bus.dispatch("llm.provider_failed", payload={"provider": config.provider, "model": config.model_name, "phase": phase, "error": str(exc), "account_id": str(account_id) if account_id else None})
            await _log_usage(session, config.provider, config.model_name, phase, (0, 0, 0), 0.0, int((monotonic() - started) * 1000), False, str(exc), account_id, config.id)
    raise HTTPException(status_code=503, detail=f"All LLM providers failed: {'; '.join(errors)}")


async def stream(session: AsyncSession, prompt: str, phase: str = "chat", system_prompt: str | None = None, account_id: UUID | None = None, **kwargs: Any) -> AsyncGenerator[SSEEvent, None]:
    request = LLMRequest(prompt=prompt, system_prompt=system_prompt, temperature=float(kwargs.get("temperature", 0.7)), max_tokens=int(kwargs.get("max_tokens", 1024)), top_p=float(kwargs.get("top_p", 1.0)), stop_sequences=kwargs.get("stop_sequences"))
    for provider, config in await get_provider_chain(session, phase):
        _, _, threshold, reset = _resilience_config(config)
        breaker = CircuitBreakerRegistry.get(f"{config.provider}:{config.id}", threshold, 1, reset)
        if not await breaker.allow_request():
            continue
        started = monotonic()
        usage_tokens: tuple[int, int, int] = (0, 0, 0)
        try:
            async for event in provider.stream(request):
                if event.event_type == "usage" and isinstance(event.data, dict):
                    usage_tokens = (int(event.data.get("prompt_tokens", 0)), int(event.data.get("completion_tokens", 0)), int(event.data.get("total_tokens", 0)))
                yield event
            await breaker.record_success()
            cost = _cost(config.cost_per_1k_tokens, usage_tokens[2])
            await _log_usage(session, config.provider, config.model_name, phase, usage_tokens, cost, int((monotonic() - started) * 1000), True, None, account_id, config.id)
            return
        except Exception as exc:  # noqa: BLE001
            await breaker.record_failure()
            await event_bus.dispatch("llm.provider_failed", payload={"provider": config.provider, "model": config.model_name, "phase": phase, "error": str(exc), "account_id": str(account_id) if account_id else None})
            cost = _cost(config.cost_per_1k_tokens, usage_tokens[2])
            await _log_usage(session, config.provider, config.model_name, phase, usage_tokens, cost, int((monotonic() - started) * 1000), False, str(exc), account_id, config.id)
    raise HTTPException(status_code=503, detail="No streaming provider available")


async def health_check_all(session: AsyncSession) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for config in await llm_provider_repository.get_all(session, active_only=False):
        try:
            provider = create_provider(config)
            results[f"{config.name}:{config.model_name}"] = await provider.health_check() if provider else False
        except Exception:
            results[f"{config.name}:{config.model_name}"] = False
    return results


async def list_provider_configs(session: AsyncSession, active_only: bool = False) -> list[LLMProviderConfigPublic]:
    return [_provider_public(config) for config in await llm_provider_repository.get_all(session, active_only)]


async def get_provider_config(session: AsyncSession, config_id: UUID) -> LLMProviderConfigPublic:
    config = await llm_provider_repository.get_by_id(session, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM provider config not found")
    return _provider_public(config)


async def create_provider_config(session: AsyncSession, data: LLMProviderConfigCreate) -> LLMProviderConfigPublic:
    payload = _create_provider_payload(data)
    if data.credential_source == CredentialSource.ENCRYPTED_DB.value and data.encrypted_api_key:
        payload["encrypted_api_key"] = encrypt_value(data.encrypted_api_key)
    result = _provider_public(await llm_provider_repository.create(session, payload))
    clear_provider_cache()
    return result


async def update_provider_config(session: AsyncSession, config_id: UUID, data: LLMProviderConfigUpdate) -> LLMProviderConfigPublic:
    payload = _update_provider_payload(data)
    if data.credential_source == CredentialSource.ENCRYPTED_DB.value and data.encrypted_api_key:
        payload["encrypted_api_key"] = encrypt_value(data.encrypted_api_key)
    config = await llm_provider_repository.update(session, config_id, payload)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM provider config not found")
    clear_provider_cache()
    return _provider_public(config)


async def delete_provider_config(session: AsyncSession, config_id: UUID) -> dict[str, bool]:
    result = {"deleted": await llm_provider_repository.delete(session, config_id)}
    clear_provider_cache()
    return result


async def get_usage_history(session: AsyncSession, account_id: UUID, skip: int = 0, limit: int = 100) -> dict[str, Any]:
    logs = [LLMUsageLogPublic.model_validate(item) for item in await llm_usage_repository.get_by_account(session, account_id, skip, limit)]
    return {"summary": await llm_usage_repository.get_cost_summary(session, account_id), "logs": logs}


async def validate_provider(session: AsyncSession, config_id: UUID) -> ValidateProviderResult:
    config = await llm_provider_repository.get_by_id(session, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM provider config not found")
    provider = create_provider(config)
    if provider is None:
        return ValidateProviderResult(valid=False, error=f"Unknown provider type: {config.provider}")
    return await provider.validate_api_key()


async def list_provider_models(session: AsyncSession, config_id: UUID) -> list[str]:
    config = await llm_provider_repository.get_by_id(session, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM provider config not found")
    provider = create_provider(config)
    if provider is None:
        return []
    return await provider.list_models()
