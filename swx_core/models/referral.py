# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class ReferralCode(Base, table=True):
    __tablename__ = "swx_referral_code"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    code: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    max_referrals: int = Field(default=100, sa_column=Column(Integer, nullable=False, server_default="100"))
    referral_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    bonus_tokens: int = Field(default=10_000, sa_column=Column(Integer, nullable=False, server_default="10000"))
    referrer_bonus_tokens: int = Field(default=10_000, sa_column=Column(Integer, nullable=False, server_default="10000"))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))


class ReferralEvent(Base, table=True):
    __tablename__ = "swx_referral_event"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    referral_code_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_referral_code.id", ondelete="CASCADE"), nullable=False, index=True))
    referred_user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    referrer_bonus_credited: bool = Field(default=False)
    referred_bonus_credited: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))