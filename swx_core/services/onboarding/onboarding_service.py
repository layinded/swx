"""Onboarding Service
--------------------
Per-user onboarding step tracking with registered step definitions
and completion percentage calculation.

Step definitions are registered, not hardcoded::

    from swx_core.services.onboarding.onboarding_service import onboarding

    onboarding.register_steps("profile", "email_verify", "first_project")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.onboarding import (
    OnboardingStep,
    OnboardingStepCreate,
    OnboardingStepPublic,
    OnboardingStepStatus,
)
from swx_core.utils.time import utc_now

logger = logging.getLogger(__name__)

_DEFAULT_STEPS: list[str] = [
    "profile",
    "email_verify",
    "first_project",
]


@dataclass
class OnboardingProgress:
    """Summary of a user's onboarding progress."""
    user_id: UUID
    total_steps: int
    completed_steps: int
    skipped_steps: int
    percentage: float
    steps: list[OnboardingStepPublic] = field(default_factory=list)


class OnboardingService:
    """Manage per-user onboarding steps.

    Steps are registered at app startup.  Each user gets a row per
    registered step when initialized.
    """

    def __init__(self) -> None:
        self._registered_steps: list[str] = list(_DEFAULT_STEPS)

    def register_steps(self, *steps: str) -> None:
        """Register onboarding step keys (idempotent)."""
        for step in steps:
            if step not in self._registered_steps:
                self._registered_steps.append(step)

    @property
    def registered_steps(self) -> list[str]:
        return list(self._registered_steps)

    async def initialize_user(self, session: AsyncSession, user_id: UUID) -> list[OnboardingStepPublic]:
        """Create pending onboarding steps for a new user."""
        existing = await self._get_existing_keys(session, user_id)
        new_keys = [k for k in self._registered_steps if k not in existing]
        steps: list[OnboardingStepPublic] = []
        for key in new_keys:
            step = OnboardingStep(
                user_id=user_id,
                step_key=key,
                status=OnboardingStepStatus.PENDING.value,
            )
            session.add(step)
            steps.append(OnboardingStepPublic.model_validate(step))
        if new_keys:
            await session.commit()
        return steps

    async def complete_step(self, session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None:
        """Mark a step as completed."""
        stmt = (
            update(OnboardingStep)
            .where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
            .values(status=OnboardingStepStatus.COMPLETED.value, completed_at=utc_now())
            .returning(OnboardingStep)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        await session.commit()
        return OnboardingStepPublic.model_validate(row)

    async def skip_step(self, session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None:
        """Mark a step as skipped."""
        stmt = (
            update(OnboardingStep)
            .where(OnboardingStep.user_id == user_id, OnboardingStep.step_key == step_key)
            .values(status=OnboardingStepStatus.SKIPPED.value)
            .returning(OnboardingStep)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        await session.commit()
        return OnboardingStepPublic.model_validate(row)

    async def get_progress(self, session: AsyncSession, user_id: UUID) -> OnboardingProgress:
        """Return onboarding progress summary for a user."""
        stmt = select(OnboardingStep).where(OnboardingStep.user_id == user_id)
        result = await session.execute(stmt)
        steps = [OnboardingStepPublic.model_validate(row) for row in result.scalars().all()]

        completed = sum(1 for s in steps if s.status == OnboardingStepStatus.COMPLETED.value)
        skipped = sum(1 for s in steps if s.status == OnboardingStepStatus.SKIPPED.value)
        total = len(self._registered_steps)
        percentage = round(((completed + skipped) / total) * 100, 1) if total else 0.0

        return OnboardingProgress(
            user_id=user_id,
            total_steps=total,
            completed_steps=completed,
            skipped_steps=skipped,
            percentage=percentage,
            steps=steps,
        )

    async def _get_existing_keys(self, session: AsyncSession, user_id: UUID) -> set[str]:
        stmt = select(OnboardingStep.step_key).where(OnboardingStep.user_id == user_id)
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}


onboarding = OnboardingService()
"""Module-level singleton. Import and use from anywhere."""