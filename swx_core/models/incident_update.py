# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IncidentUpdateBase(Base):
    incident_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_status_incident.id"), nullable=False, index=True))
    message: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="investigating", max_length=20)


class IncidentUpdate(IncidentUpdateBase, table=True):
    __tablename__ = "swx_incident_update"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False))
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class IncidentUpdateCreate(SQLModel):
    message: str
    status: str = Field(default="investigating", max_length=20)


class IncidentUpdatePublic(SQLModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    message: str
    status: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}