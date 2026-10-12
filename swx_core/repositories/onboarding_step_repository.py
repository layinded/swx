"""Onboarding Step Repository
----------------------------
Data access for onboarding step tracking.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.onboarding import OnboardingStep


async def create(session: AsyncSession, data: dict[str, Any]) -> OnboardingStep:
    step = OnboardingStep(**data)
    session.add(step)
    await session.flush()
    return step


async def get_by_id(session: AsyncSession, step_id: uuid.UUID) -> Optional[OnboardingStep]:
    return await session.get(OnboardingStep, step_id)


async def get_by_user_and_key(session: AsyncSession, user_id: uuid.UUID, step_key: str) -> Optional[OnboardingStep]:
    stmt = select(OnboardingStep).where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_by_user(session: AsyncSession, user_id: uuid.UUID) -> list[OnboardingStep]:
    stmt = select(OnboardingStep).where(OnboardingStep.user_id == user_id).order_by(OnboardingStep.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())