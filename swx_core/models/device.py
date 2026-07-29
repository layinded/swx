"""Device registration model for push notification tokens."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel, Relationship

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class DevicePlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNREGISTERED = "unregistered"


class DeviceBase(Base):
    platform: DevicePlatform = Field(default=DevicePlatform.IOS)
    fcm_token: str = Field(max_length=500)
    device_name: str | None = Field(default=None, max_length=200)
    device_model: str | None = Field(default=None, max_length=200)
    os_version: str | None = Field(default=None, max_length=50)
    app_version: str | None = Field(default=None, max_length=20)
    status: DeviceStatus = Field(default=DeviceStatus.ACTIVE)
    is_primary: bool = Field(default=False)
    last_used_at: datetime | None = None


class Device(DeviceBase, table=True):
    __tablename__ = "swx_device"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    platform: DevicePlatform = Field(
        sa_column=Column(String(20), nullable=False, server_default="ios", index=True)
    )
    fcm_token: str = Field(sa_column=Column(String(500), nullable=False, index=True))
    status: DeviceStatus = Field(
        sa_column=Column(String(20), nullable=False, server_default="active", index=True)
    )
    is_primary: bool = Field(
        sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    extra_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )

    user: "User" = Relationship()  # type: ignore


class DeviceCreate(SQLModel):
    platform: DevicePlatform = DevicePlatform.IOS
    fcm_token: str = Field(max_length=500)
    device_name: str | None = None
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    is_primary: bool = False
    extra_data: dict[str, Any] = Field(default_factory=dict)


class DeviceUpdate(SQLModel):
    fcm_token: str | None = Field(default=None, max_length=500)
    device_name: str | None = None
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    status: DeviceStatus | None = None
    is_primary: bool | None = None
    last_used_at: datetime | None = None
    extra_data: dict[str, Any] | None = None


class DevicePublic(DeviceBase):
    id: uuid.UUID
    user_id: uuid.UUID
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DevicesPublic(SQLModel):
    data: list[DevicePublic]
    count: int