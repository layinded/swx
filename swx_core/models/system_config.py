"""
System Configuration Model
--------------------------
This module defines the SystemConfig model for runtime system settings.

SystemConfig stores runtime-tunable settings that can be changed without redeployment.
Secrets and infrastructure settings remain in .env files.

Features:
- Type-safe value storage (int, bool, string, json)
- Category-based organization
- Audit trail (updated_by, updated_at)
- Change history support
- Validation guards
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from sqlalchemy import Column, DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class SettingValueType(str, Enum):
    """Type of setting value for type safety."""
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    JSON = "json"


class SettingCategory(str, Enum):
    """Category for organizing settings."""
    SECURITY = "security"
    RATE_LIMIT = "rate_limit"
    FEATURE_FLAG = "feature_flag"
    EMAIL = "email"
    JOBS = "jobs"
    POLICY = "policy"
    AUDIT = "audit"
    GENERAL = "general"


class SystemConfigBase(Base):
    """
    Base model for system configuration fields.
    
    Attributes:
        key (str): Unique setting key (e.g., "auth.access_token_expire_minutes").
        value (str): Setting value stored as string (JSON for complex types).
        value_type (SettingValueType): Type of the value for validation.
        category (SettingCategory): Category for organization.
        description (str): Human-readable description.
        is_sensitive (bool): Always False - secrets never in DB.
        is_active (bool): Can be deactivated without deletion.
        updated_by (str): Admin email or "system" for automated updates.
        updated_at (datetime): Last update timestamp.
        metadata (dict): Additional metadata (JSON).
    """
    
    key: str = Field(unique=True, index=True, max_length=255)
    value: Any = Field(sa_column=Column(JSONB, nullable=False, server_default=text("'null'::jsonb")))
    value_type: SettingValueType = Field(default=SettingValueType.STRING, index=True)
    category: SettingCategory = Field(default=SettingCategory.GENERAL, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_sensitive: bool = Field(default=False)  # Always False - validation enforces
    is_active: bool = Field(default=True, index=True)
    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False),
        alias="metadata",
    )


class SystemConfig(SystemConfigBase, table=True):
    """
    System configuration table for runtime settings.
    
    Stores runtime-tunable settings that can be changed without redeployment.
    Secrets and infrastructure settings remain in .env files.
    """
    __tablename__ = "swx_system_config"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class SystemConfigCreate(SQLModel):
    """Schema for creating a system setting."""
    key: str = Field(max_length=255)
    value: Any
    value_type: SettingValueType = SettingValueType.STRING
    category: SettingCategory = SettingCategory.GENERAL
    description: Optional[str] = Field(default=None, max_length=1000)
    metadata: Optional[dict[str, Any]] = None  # pyright: ignore[reportIncompatibleVariableOverride]


class SystemConfigUpdate(SQLModel):
    """Schema for updating a system setting."""
    value: Optional[Any] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None  # pyright: ignore[reportIncompatibleVariableOverride]


class SystemConfigPublic(SQLModel):
    """Public schema for system settings (excludes sensitive fields)."""
    id: uuid.UUID
    key: str
    value: Any
    value_type: SettingValueType
    category: SettingCategory
    description: Optional[str]
    is_active: bool
    updated_at: datetime
    updated_by: Optional[str]
    metadata: dict[str, Any]  # pyright: ignore[reportIncompatibleVariableOverride]


class SystemConfigHistory(Base, table=True):
    """
    Change history for system settings (append-only).
    
    Tracks all changes to settings for audit purposes.
    """
    __tablename__ = "swx_system_config_history"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    config_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_system_config.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    key: str = Field(index=True, max_length=255)
    old_value: Optional[Any] = Field(default=None, sa_column=Column(JSONB, nullable=True))
    new_value: Any = Field(sa_column=Column(JSONB, nullable=False))
    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )
    change_reason: Optional[str] = Field(default=None, max_length=500)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False),
        alias="metadata",
    )


DEFAULT_SYSTEM_CONFIGS: list[dict[str, Any]] = [
    {
        "key": "auth.access_token_expire_minutes",
        "value": 10080,
        "value_type": SettingValueType.INT,
        "category": SettingCategory.SECURITY,
        "description": "Access token expiration in minutes (7 days default)",
        "is_active": True,
    },
    {
        "key": "auth.refresh_token_expire_days",
        "value": 30,
        "value_type": SettingValueType.INT,
        "category": SettingCategory.SECURITY,
        "description": "Refresh token expiration in days",
        "is_active": True,
    },
    {
        "key": "rate_limit.enabled",
        "value": True,
        "value_type": SettingValueType.BOOL,
        "category": SettingCategory.RATE_LIMIT,
        "description": "Enable rate limiting globally",
        "is_active": True,
    },
    {
        "key": "rate_limit.fail_open",
        "value": False,
        "value_type": SettingValueType.BOOL,
        "category": SettingCategory.RATE_LIMIT,
        "description": "Allow requests when Redis is unavailable",
        "is_active": True,
    },
    {
        "key": "feature.social_login_enabled",
        "value": False,
        "value_type": SettingValueType.BOOL,
        "category": SettingCategory.FEATURE_FLAG,
        "description": "Enable OAuth social login",
        "is_active": True,
    },
    {
        "key": "jobs.max_concurrent",
        "value": 10,
        "value_type": SettingValueType.INT,
        "category": SettingCategory.JOBS,
        "description": "Maximum concurrent background jobs",
        "is_active": True,
    },
    {
        "key": "audit.log_retention_days",
        "value": 90,
        "value_type": SettingValueType.INT,
        "category": SettingCategory.AUDIT,
        "description": "Days to retain audit logs before cleanup",
        "is_active": True,
    },
    {
        "key": "policy.min_password_length",
        "value": 8,
        "value_type": SettingValueType.INT,
        "category": SettingCategory.POLICY,
        "description": "Minimum password length",
        "is_active": True,
    },
    {
        "key": "email.enabled",
        "value": True,
        "value_type": SettingValueType.BOOL,
        "category": SettingCategory.EMAIL,
        "description": "Enable email notifications globally",
        "is_active": True,
    },
    {
        "key": "general.maintenance_mode",
        "value": False,
        "value_type": SettingValueType.BOOL,
        "category": SettingCategory.GENERAL,
        "description": "Maintenance mode — returns 503 on non-health endpoints",
        "is_active": True,
    },
]
