"""
Audit Log Model
---------------
This module defines the AuditLog model for tracking security and business-relevant events.

Audit logs are immutable and append-only. No updates or deletes are allowed.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class AuditLogBase(Base):
    """
    Base model for audit log fields.
    """
    actor_type: str = Field(index=True, max_length=50)  # system | admin | user
    actor_id: Optional[str] = Field(default=None, index=True, max_length=255)
    action: str = Field(index=True, max_length=255)
    resource_type: Optional[str] = Field(default=None, index=True, max_length=255)
    resource_id: Optional[str] = Field(default=None, index=True, max_length=255)
    outcome: str = Field(index=True, max_length=50)  # success | failure
    ip_address: Optional[str] = Field(default=None, max_length=50)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    request_id: Optional[str] = Field(default=None, index=True, max_length=255)
    # Using 'context' instead of 'metadata' to avoid conflict with SQLAlchemy MetaData
    context: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    )


class AuditLog(AuditLogBase, table=True):
    """
    Database model representing an audit log entry.
    """
    __tablename__ = "audit_log"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
            index=True
        )
    )


class AuditLogPublic(AuditLogBase):
    """
    Public schema for exposing audit log data.
    """
    id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogsPublic(SQLModel):
    """
    Schema for a list of public audit logs.
    """
    data: list[AuditLogPublic]
    count: int
