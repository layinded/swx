# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Compliance, GDPR & SOC 2 Settings Mixin.

Defines compliance-related settings: SOC 2 backup status, SIEM integration,
API key scoping, session management, and feature flags.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class ComplianceSettingsMixin(BaseSettings):
    """Compliance, GDPR and SOC 2 configuration."""

    # Backup Status (SOC 2 CC6.5)
    BACKUP_STATUS_URL: str | None = Field(
        default=None,
        description="External backup system URL for SOC 2 backup verification.",
    )

    # SIEM Integration (SOC 2 CC7.2)
    SIEM_ENABLED: bool = Field(default=False, description="Enable SIEM webhook integration for critical audit events")
    SIEM_WEBHOOK_URL: str | None = Field(default=None, description="Webhook URL for SIEM integration")
    SIEM_BATCH_INTERVAL: int = Field(default=60, description="Seconds between batches of non-critical events sent to SIEM")

    # Session Management (SOC 2 CC6.1)
    MAX_CONCURRENT_SESSIONS: int = Field(default=5, description="Maximum concurrent active sessions per user")
    SESSION_IDLE_TIMEOUT_MINUTES: int = Field(default=60, description="Minutes of inactivity before session expires")
    SESSION_IDLE_CLEANUP_INTERVAL_SECONDS: int = Field(default=3600, description="Seconds between idle session cleanup cycles")
    API_KEY_LIFECYCLE_INTERVAL_SECONDS: int = Field(default=86400, description="Seconds between API key lifecycle cleanup cycles")

    # Feature Flags & A/B Testing
    FEATURE_FLAG_ENABLED: bool = Field(default=True, description="Enable feature flags and A/B testing")

    # API Key Scoping Settings
    API_KEY_ENABLED: bool = True
    API_KEY_DEFAULT_EXPIRY_DAYS: int = 90
    API_KEY_MAX_EXPIRY_DAYS: int = 365
    API_KEY_MAX_INACTIVE_DAYS: int = 180
    API_KEY_ROTATION_GRACE_HOURS: int = 24
    API_KEY_DEFAULT_RATE_LIMIT: int = 60
    API_KEY_CACHE_TTL: int = 300
