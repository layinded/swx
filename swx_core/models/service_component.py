# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ServiceComponentBase(Base):
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="operational", max_length=20)
    group_name: str | None = Field(default=None, max_length=100)
    sort_order: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    uptime_percentage: float | None = Field(default=None)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))


class ServiceComponent(ServiceComponentBase, table=True):
    __tablename__ = "swx_service_component"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now()))


class ServiceComponentCreate(SQLModel):
    name: str = Field(max_length=200)
    description: str | None = None
    status: str = Field(default="operational", max_length=20)
    group_name: str | None = None
    sort_order: int = 0
    uptime_percentage: float | None = None
    metadata_: dict[str, Any] | None = None


class ServiceComponentUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    group_name: str | None = None
    sort_order: int | None = None
    uptime_percentage: float | None = None
    metadata_: dict[str, Any] | None = None


class ServiceComponentPublic(SQLModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    group_name: str | None = None
    sort_order: int
    uptime_percentage: float | None = None
    metadata_: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}