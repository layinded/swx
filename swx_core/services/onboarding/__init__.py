"""Onboarding Service
--------------------
Per-user onboarding step tracking.  Step definitions are registered at
startup (not hardcoded), and the service computes completion percentage
from the registered step keys.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.onboarding import (
    OnboardingStep,
    OnboardingStepCreate,
    OnboardingStepPublic,
    OnboardingStepStatus,
)
from swx_core.utils.time import utc_now

logger = logging.getLogger(__name__)

_REGISTERED_STEPS: list[str] = []


def register_onboarding_steps(steps: list[str]) -> None:
    global _REGISTERED_STEPS
    _REGISTERED_STEPS = list(steps)
    logger.info("Registered %d onboarding steps: %s", len(steps), steps)


def get_registered_steps() -> list[str]:
    return list(_REGISTERED_STEPS)


def _to_public(step: OnboardingStep) -> OnboardingStepPublic:
    return OnboardingStepPublic.model_validate(step)


async def initialize_steps(session: AsyncSession, user_id: UUID) -> list[OnboardingStepPublic]:
    if not _REGISTERED_STEPS:
        return []

    existing = (await session.execute(
        select(OnboardingStep.step_key).where(OnboardingStep.user_id == user_id)
    )).scalars().all()

    created: list[OnboardingStepPublic] = []
    for step_key in _REGISTERED_STEPS:
        if step_key in existing:
            continue
        step = OnboardingStep(user_id=user_id, step_key=step_key, status=OnboardingStepStatus.PENDING.value)
        session.add(step)
        created.append(_to_public(step))

    if created:
        await session.commit()

    return created


async def complete_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None:
    stmt = (
        update(OnboardingStep)
        .where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
        .values(status=OnboardingStepStatus.COMPLETED.value, completed_at=utc_now())
    )
    result = await session.execute(stmt)
    await session.commit()

    if result.rowcount == 0:
        return None

    step = (await session.execute(
        select(OnboardingStep).where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
    )).scalar_one_or_none()
    return _to_public(step) if step else None


async def skip_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None:
    stmt = (
        update(OnboardingStep)
        .where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
        .values(status=OnboardingStepStatus.SKIPPED.value, completed_at=utc_now())
    )
    result = await session.execute(stmt)
    await session.commit()

    step = (await session.execute(
        select(OnboardingStep).where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
    )).scalar_one_or_none()
    return _to_public(step) if step else None


async def get_progress(session: AsyncSession, user_id: UUID) -> dict:
    total_registered = len(_REGISTERED_STEPS) or 1
    steps = (await session.execute(
        select(OnboardingStep).where(OnboardingStep.user_id == user_id)
    )).scalars().all()

    completed = sum(1 for s in steps if s.status == OnboardingStepStatus.COMPLETED.value)
    skipped = sum(1 for s in steps if s.status == OnboardingStepStatus.SKIPPED.value)
    done = completed + skipped
    percentage = round((done / total_registered) * 100, 1) if total_registered else 0.0

    return {
        "user_id": str(user_id),
        "total_steps": total_registered,
        "completed": completed,
        "skipped": skipped,
        "percentage": percentage,
        "steps": [
            {"step_key": s.step_key, "status": s.status, "completed_at": s.completed_at.isoformat() if s.completed_at else None}
            for s in steps
        ],
    }
