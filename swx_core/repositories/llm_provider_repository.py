# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.llm_provider_config import LLMProviderConfig

class LLMProviderConfigData(TypedDict, total=False):
    provider: str
    name: str
    model_name: str
    credentials: dict[str, Any]
    default_params: dict[str, Any]
    priority: int
    is_primary: bool
    is_active: bool
    supported_phases: list[str]
    cost_per_1k_tokens: float | None
    supports_streaming: bool
    supports_json_mode: bool
    timeout_seconds: int | None
    max_retries: int | None
    circuit_breaker_threshold: int | None
    circuit_breaker_reset_seconds: int | None
    rate_limit_per_minute: int | None
    daily_token_limit: int | None
    credential_source: str
    encrypted_api_key: str | None
    extra_data: dict[str, Any]
    updated_at: datetime

async def create(session: AsyncSession, data: LLMProviderConfigData) -> LLMProviderConfig:
    config = LLMProviderConfig(**data)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config

async def get_by_id(session: AsyncSession, config_id: UUID) -> LLMProviderConfig | None:
    stmt = select(LLMProviderConfig).where(LLMProviderConfig.id == config_id)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_all(session: AsyncSession, active_only: bool = False, team_id: UUID | None = None) -> list[LLMProviderConfig]:
    stmt = select(LLMProviderConfig)
    if active_only:
        stmt = stmt.where(LLMProviderConfig.is_active == True)  # pyright: ignore[reportArgumentType]
    if team_id is not None:
        stmt = stmt.where(LLMProviderConfig.team_id == team_id)
    priority_column = getattr(LLMProviderConfig, "priority")
    name_column = getattr(LLMProviderConfig, "name")
    stmt = stmt.order_by(priority_column, name_column)
    return list((await session.execute(stmt)).scalars().all())

async def get_by_provider(session: AsyncSession, provider_type: str, team_id: UUID | None = None) -> list[LLMProviderConfig]:
    priority_column = getattr(LLMProviderConfig, "priority")
    stmt = select(LLMProviderConfig).where(LLMProviderConfig.provider == provider_type)  # pyright: ignore[reportArgumentType]
    if team_id is not None:
        stmt = stmt.where(LLMProviderConfig.team_id == team_id)
    stmt = stmt.order_by(priority_column)
    return list((await session.execute(stmt)).scalars().all())

async def get_primary_for_phase(session: AsyncSession, phase: str) -> LLMProviderConfig | None:
    return next((config for config in await get_all(session, active_only=True) if config.is_primary and phase in config.supported_phases), None)

async def get_fallbacks_for_phase(session: AsyncSession, phase: str, exclude_id: UUID | None = None) -> list[LLMProviderConfig]:
    configs = await get_all(session, active_only=True)
    return [config for config in configs if phase in config.supported_phases and config.id != exclude_id]

async def update(session: AsyncSession, config_id: UUID, data: LLMProviderConfigData) -> LLMProviderConfig | None:
    config = await get_by_id(session, config_id)
    if config is None:
        return None
    for key, value in {**data, "updated_at": utc_now()}.items():
        setattr(config, key, value)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config

async def delete(session: AsyncSession, config_id: UUID) -> bool:
    config = await get_by_id(session, config_id)
    if config is None:
        return False
    await session.delete(config)
    await session.commit()
    return True

async def set_primary(session: AsyncSession, config_id: UUID, phase: str) -> None:
    configs = await get_all(session, active_only=False)
    for config in configs:
        if phase not in config.supported_phases:
            continue
        config.is_primary = config.id == config_id
        config.updated_at = utc_now()
        session.add(config)
    await session.commit()
