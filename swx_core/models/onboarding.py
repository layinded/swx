# pyright: reportUnannotatedClassAttribute=false, reportMissingTypeArgument=false, reportAssignmentType=false

"""Onboarding Step Model
------------------------
Per-user onboarding step tracking.  Steps are registered (not hardcoded)
and track completion state for new-user onboarding flows.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class OnboardingStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class OnboardingStepBase(Base):
    step_key: str = Field(max_length=100, index=True)
    status: str = Field(default=OnboardingStepStatus.PENDING.value, max_length=20)
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class OnboardingStep(OnboardingStepBase, table=True):
    __tablename__ = "swx_onboarding_step"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_onboarding_step_user_key", "user_id", "step_key", unique=True),
        {"extend_existing": True},
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=text("now()")),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()")),
    )


class OnboardingStepCreate(SQLModel):
    step_key: str = Field(max_length=100)
    user_id: uuid.UUID


class OnboardingStepUpdate(SQLModel):
    status: Optional[str] = None


class OnboardingStepPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    step_key: str
    status: str
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True