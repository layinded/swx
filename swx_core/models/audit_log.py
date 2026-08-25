# pyright: reportUnannotatedClassAttribute=false, reportMissingTypeArgument=false, reportAssignmentType=false

"""
Audit Log Model
---------------

SOC 2 CC7.2 compliant audit logging with tamper-evident hash chain.

Every AuditLog entry includes a SHA-256 ``log_hash`` computed from
the previous entry's hash concatenated with the current entry's
canonical fields.  Breaking the chain proves tampering; verifying
the chain proves integrity.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime, String, text
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
    severity: Optional[str] = Field(default="info", index=True, max_length=20)
    data_classification: Optional[str] = Field(default=None, index=True, max_length=50)
    access_result: Optional[str] = Field(default=None, index=True, max_length=50)
    ip_address: Optional[str] = Field(default=None, max_length=50)
    masked_ip: Optional[str] = Field(default=None, max_length=50)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    request_id: Optional[str] = Field(default=None, index=True, max_length=255)
    # Using 'context' instead of 'metadata' to avoid conflict with SQLAlchemy MetaData
    context: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    )


class AuditLog(AuditLogBase, table=True):
    """
    Database model representing an audit log entry.
    """
    __tablename__ = "swx_audit_log"  # pyright: ignore[reportAssignmentType]
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
    log_hash: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True, index=True),
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
