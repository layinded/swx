# pyright: reportAny=false, reportUnknownVariableType=false

from typing import TypedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, func, select

from swx_core.models.llm_usage_log import LLMUsageLog


class LLMUsageLogData(TypedDict, total=False):
    provider_config_id: UUID | None
    provider: str
    model_name: str
    phase: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    success: bool
    error_message: str | None
    account_id: UUID | None


async def create(session: AsyncSession, data: LLMUsageLogData) -> LLMUsageLog:
    log = LLMUsageLog(**data)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_by_account(session: AsyncSession, account_id: UUID, skip: int = 0, limit: int = 100) -> list[LLMUsageLog]:
    stmt = (
        select(LLMUsageLog)
        .where(LLMUsageLog.account_id == account_id)
        .order_by(desc(LLMUsageLog.created_at))
        .offset(skip)
        .limit(limit)
    )  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def get_cost_summary(session: AsyncSession, account_id: UUID) -> dict[str, float | int]:
    stmt = (
        select(
            func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
            func.count(LLMUsageLog.id),  # pyright: ignore[reportArgumentType]
        )
        .where(LLMUsageLog.account_id == account_id)
    )  # pyright: ignore[reportArgumentType]
    total_cost, total_tokens, count = (await session.execute(stmt)).one()
    return {"total_cost": float(total_cost or 0.0), "total_tokens": int(total_tokens or 0), "count": int(count or 0)}
