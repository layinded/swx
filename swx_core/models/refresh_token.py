from dataclasses import dataclass
import uuid
from datetime import datetime
from typing import Any, Optional, cast

from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class RefreshTokenBase(Base):
    token: str = Field(..., nullable=False)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class RefreshToken(RefreshTokenBase, table=True):
    __tablename__ = cast(Any, "swx_refresh_token")
    __table_args__ = cast(Any, {"extend_existing": True})

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_email: str = Field(index=True)
    device_info: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    ip_address: str | None = Field(default=None, sa_column=Column(String(45), nullable=True))
    last_activity_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class RefreshTokenCreate(RefreshTokenBase):
    pass


class RefreshTokenUpdate(RefreshTokenBase):
    pass


class RefreshTokenPublic(RefreshToken):
    pass


@dataclass
class SessionPublic:
    """Public schema for exposing session info (no token value)."""
    id: uuid.UUID
    user_email: str
    device_info: str | None
    ip_address: str | None
    created_at: datetime
    last_activity_at: datetime | None
    expires_at: datetime
    is_expired: bool