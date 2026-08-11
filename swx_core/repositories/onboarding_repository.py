"""Onboarding Step Repository
----------------------------
Data access for onboarding step records.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.onboarding import OnboardingStep, OnboardingStepStatus


async def get_steps_by_user(session: AsyncSession, user_id: UUID) -> list[OnboardingStep]:
    stmt = select(OnboardingStep).where(OnboardingStep.user_id == user_id).order_by(OnboardingStep.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_step(session: AsyncSession, step_id: UUID) -> OnboardingStep | None:
    return await session.get(OnboardingStep, step_id)


async def create_step(session: AsyncSession, data: dict[str, Any]) -> OnboardingStep:
    step = OnboardingStep(**data)
    session.add(step)
    await session.commit()
    await session.refresh(step)
    return step


async def update_step(session: AsyncSession, step_id: UUID, data: dict[str, Any]) -> OnboardingStep | None:
    step = await session.get(OnboardingStep, step_id)
    if step is None:
        return None
    for key, value in data.items():
        setattr(step, key, value)
    await session.commit()
    await session.refresh(step)
    return step


async def delete_step(session: AsyncSession, step_id: UUID) -> bool:
    step = await session.get(OnboardingStep, step_id)
    if step is None:
        return False
    await session.delete(step)
    await session.commit()
    return True


async def complete_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStep | None:
    stmt = select(OnboardingStep).where(
        OnboardingStep.user_id == user_id,
        OnboardingStep.step_key == step_key,
    )
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        return None
    step.status = OnboardingStepStatus.COMPLETED.value
    step.completed_at = utc_now()
    session.add(step)
    await session.commit()
    await session.refresh(step)
    return step


async def skip_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStep | None:
    stmt = select(OnboardingStep).where(
        OnboardingStep.user_id == user_id,
        OnboardingStep.step_key == step_key,
    )
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        return None
    step.status = OnboardingStepStatus.SKIPPED.value
    session.add(step)
    await session.commit()
    await session.refresh(step)
    return step


from swx_core.utils.time import utc_now  # noqa: E402