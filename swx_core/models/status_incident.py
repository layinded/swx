# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StatusIncidentBase(Base):
    title: str = Field(max_length=500)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    severity: str = Field(default="investigating", max_length=20)
    status: str = Field(default="open", max_length=20)
    component_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_service_component.id"), nullable=True))
    started_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))


class StatusIncident(StatusIncidentBase, table=True):
    __tablename__ = "swx_status_incident"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False))
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now()))


class StatusIncidentCreate(SQLModel):
    title: str = Field(max_length=500)
    description: str | None = None
    severity: str = Field(default="investigating", max_length=20)
    status: str = Field(default="open", max_length=20)
    component_id: uuid.UUID | None = None
    started_at: datetime | None = None
    metadata_: dict[str, Any] | None = None


class StatusIncidentUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    component_id: uuid.UUID | None = None
    resolved_at: datetime | None = None
    metadata_: dict[str, Any] | None = None


class StatusIncidentPublic(SQLModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    severity: str
    status: str
    component_id: uuid.UUID | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    metadata_: dict[str, Any] | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}