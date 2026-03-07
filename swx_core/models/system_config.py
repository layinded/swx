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
from sqlalchemy import Column, String, Text, JSON
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


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
    value: str = Field(max_length=5000)  # Store as string, parse by value_type
    value_type: SettingValueType = Field(default=SettingValueType.STRING, index=True)
    category: SettingCategory = Field(default=SettingCategory.GENERAL, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_sensitive: bool = Field(default=False)  # Always False - validation enforces
    is_active: bool = Field(default=True, index=True)
    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
        alias="metadata",
    )


class SystemConfig(SystemConfigBase, table=True):
    """
    System configuration table for runtime settings.
    
    Stores runtime-tunable settings that can be changed without redeployment.
    Secrets and infrastructure settings remain in .env files.
    """
    __tablename__ = "system_config"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class SystemConfigCreate(SQLModel):
    """Schema for creating a system setting."""
    key: str = Field(max_length=255)
    value: str = Field(max_length=5000)
    value_type: SettingValueType = SettingValueType.STRING
    category: SettingCategory = SettingCategory.GENERAL
    description: Optional[str] = Field(default=None, max_length=1000)
    metadata: Optional[dict[str, Any]] = None


class SystemConfigUpdate(SQLModel):
    """Schema for updating a system setting."""
    value: Optional[str] = Field(default=None, max_length=5000)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class SystemConfigPublic(SQLModel):
    """Public schema for system settings (excludes sensitive fields)."""
    id: uuid.UUID
    key: str
    value: str
    value_type: SettingValueType
    category: SettingCategory
    description: Optional[str]
    is_active: bool
    updated_at: datetime
    updated_by: Optional[str]
    metadata: dict[str, Any]


class SystemConfigHistory(Base, table=True):
    """
    Change history for system settings (append-only).
    
    Tracks all changes to settings for audit purposes.
    """
    __tablename__ = "system_config_history"
    __table_args__ = {"extend_existing": True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    config_id: uuid.UUID = Field(foreign_key="system_config.id", index=True)
    key: str = Field(index=True, max_length=255)
    old_value: Optional[str] = Field(default=None, max_length=5000)
    new_value: str = Field(max_length=5000)
    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    change_reason: Optional[str] = Field(default=None, max_length=500)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
        alias="metadata",
    )
