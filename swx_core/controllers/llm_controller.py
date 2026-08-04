from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.contracts.llm import SSEEvent, ValidateProviderResult
from swx_core.models.llm_provider_config import LLMProviderConfigCreate, LLMProviderConfigPublic, LLMProviderConfigUpdate
from swx_core.services.llm import llm_service


async def create_provider_controller(session: AsyncSession, data: LLMProviderConfigCreate) -> LLMProviderConfigPublic:
    return await llm_service.create_provider_config(session, data)


async def list_providers_controller(session: AsyncSession, active_only: bool = False) -> list[LLMProviderConfigPublic]:
    return await llm_service.list_provider_configs(session, active_only)


async def get_provider_controller(session: AsyncSession, config_id: UUID) -> LLMProviderConfigPublic:
    return await llm_service.get_provider_config(session, config_id)


async def update_provider_controller(session: AsyncSession, config_id: UUID, data: LLMProviderConfigUpdate) -> LLMProviderConfigPublic:
    return await llm_service.update_provider_config(session, config_id, data)


async def delete_provider_controller(session: AsyncSession, config_id: UUID) -> dict[str, bool]:
    return await llm_service.delete_provider_config(session, config_id)


async def generate_controller(session: AsyncSession, prompt: str, phase: str, system_prompt: str | None = None, json_mode: bool = False, account_id: UUID | None = None, **kwargs: Any) -> dict[str, Any]:
    return await llm_service.generate(session, prompt, phase, system_prompt, json_mode, account_id, **kwargs)


async def stream_controller(session: AsyncSession, prompt: str, phase: str, system_prompt: str | None = None, account_id: UUID | None = None, **kwargs: Any) -> AsyncGenerator[SSEEvent, None]:
    async for event in llm_service.stream(session, prompt, phase, system_prompt, account_id, **kwargs):
        yield event


async def health_controller(session: AsyncSession) -> dict[str, bool]:
    return await llm_service.health_check_all(session)


async def usage_controller(session: AsyncSession, account_id: UUID, skip: int = 0, limit: int = 100) -> dict[str, Any]:
    return await llm_service.get_usage_history(session, account_id, skip, limit)


async def validate_provider_controller(session: AsyncSession, config_id: UUID) -> ValidateProviderResult:
    return await llm_service.validate_provider(session, config_id)


async def list_models_controller(session: AsyncSession, config_id: UUID) -> list[str]:
    return await llm_service.list_provider_models(session, config_id)
