# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Application Settings Configuration
----------------------------------
This module defines the global settings for the SwX-API.

Features:
- Reads environment variables from `.env` file.
- Configures API, database, security, email, and CORS settings.
- Provides dynamic property-based settings.

The `Settings` class is composed from modular mixins that each define a
coherent group of settings:
- ApiSettingsMixin: API, routing, hosts, environment, logging
- SecuritySettingsMixin: auth tokens, secrets, account lockout
- EncryptionSettingsMixin: at-rest field encryption
- DatabaseSettingsMixin: database connection and pooling
- InfraSettingsMixin: CORS, email, Redis, cookies, rate limiting, CSRF, caches
- FeaturesSettingsMixin: feature toggles and framework configuration
- ComplianceSettingsMixin: compliance, SIEM, API key scoping
"""

from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

from swx_core.config.settings_api import ApiSettingsMixin
from swx_core.config.settings_compliance import ComplianceSettingsMixin
from swx_core.config.settings_database import DatabaseSettingsMixin
from swx_core.config.settings_encryption import EncryptionSettingsMixin
from swx_core.config.settings_features import FeaturesSettingsMixin
from swx_core.config.settings_infra import InfraSettingsMixin
from swx_core.config.settings_security import SecuritySettingsMixin


class Settings(
    ComplianceSettingsMixin,
    FeaturesSettingsMixin,
    InfraSettingsMixin,
    DatabaseSettingsMixin,
    EncryptionSettingsMixin,
    SecuritySettingsMixin,
    ApiSettingsMixin,
    BaseSettings,
):
    """
    Application-wide settings, loaded from environment variables or `.env` file.

    Composed from modular mixins; see each mixin's docstring for the fields
    it contributes. Kept as a single `BaseSettings` subclass so all settings
    read from `.env` in one pass and expose a unified `settings` instance.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


# Instantiate settings
settings = Settings()  # pyright: ignore[reportCallIssue]

# Compliance Audit Settings
COMPLIANCE_ENABLED: bool = True
COMPLIANCE_DEFAULT_SEVERITY: str = "info"
COMPLIANCE_DEFAULT_DATA_CLASSIFICATION: str = "PUBLIC"
COMPLIANCE_DEFAULT_IP_MASKING: str = "partial"  # full | partial | none
COMPLIANCE_DEFAULT_RETENTION_DAYS: int = 365
COMPLIANCE_AUTO_MASK_IP: bool = True
COMPLIANCE_AUTO_REDACT_FIELDS: bool = True
COMPLIANCE_DATA_SUBJECT_REQUEST_EXPIRY_DAYS: int = 30

# GDPR Settings
GDPR_ENABLED: bool = True
GDPR_DELETION_GRACE_DAYS: int = 30
GDPR_EXPORT_FORMAT: str = "json"
GDPR_ANONYMIZE_ON_DELETE: bool = True
GDPR_SOLE_OWNER_BLOCK: bool = True
GDPR_EXPORT_EXPIRY_DAYS: int = 7
GDPR_MIN_VERIFICATION_DAYS: int = 1

# Notification Settings
NOTIFICATION_ENABLED: bool = True
NOTIFICATION_DEFAULT_FROM_EMAIL: str = "noreply@example.com"
NOTIFICATION_DEFAULT_FROM_NAME: str = "SwX App"
NOTIFICATION_DEFAULT_RETRY_COUNT: int = 3
NOTIFICATION_DEFAULT_TIMEOUT: int = 30
NOTIFICATION_PROVIDER_CACHE_TTL: int = 30
NOTIFICATION_TEMPLATE_CACHE_TTL: int = 30
NOTIFICATION_RATE_LIMIT_DAILY: int = 100
NOTIFICATION_RATE_LIMIT_HOURLY: int = 20
NOTIFICATION_TEMPLATE_DIR: str = settings.NOTIFICATION_TEMPLATE_DIR
NOTIFICATION_CELERY_TASK_PATH: str = settings.NOTIFICATION_CELERY_TASK_PATH

# API Key Scoping Settings
API_KEY_ENABLED: bool = True
API_KEY_DEFAULT_EXPIRY_DAYS: int = 90
API_KEY_MAX_EXPIRY_DAYS: int = 365
API_KEY_MAX_INACTIVE_DAYS: int = 180
API_KEY_ROTATION_GRACE_HOURS: int = 24
API_KEY_DEFAULT_RATE_LIMIT: int = 60
API_KEY_CACHE_TTL: int = 300

# Webhook Settings
WEBHOOK_ENABLED: bool = settings.WEBHOOK_ENABLED
WEBHOOK_DEFAULT_RETRY_COUNT: int = settings.WEBHOOK_DEFAULT_RETRY_COUNT
WEBHOOK_DEFAULT_RETRY_DELAY: int = settings.WEBHOOK_DEFAULT_RETRY_DELAY
WEBHOOK_DEFAULT_TIMEOUT: int = settings.WEBHOOK_DEFAULT_TIMEOUT
WEBHOOK_MAX_RETRIES: int = settings.WEBHOOK_MAX_RETRIES
WEBHOOK_CIRCUIT_BREAKER_THRESHOLD: int = settings.WEBHOOK_CIRCUIT_BREAKER_THRESHOLD

# Conversation State Settings
CONVERSATION_ENABLED: bool = settings.CONVERSATION_ENABLED
CONVERSATION_DEFAULT_PAGE_SIZE: int = settings.CONVERSATION_DEFAULT_PAGE_SIZE
CONVERSATION_MAX_MESSAGE_LENGTH: int = settings.CONVERSATION_MAX_MESSAGE_LENGTH
CONVERSATION_CACHE_TTL: int = settings.CONVERSATION_CACHE_TTL

# AI Safety Settings
SAFETY_ENABLED: bool = settings.SAFETY_ENABLED
SAFETY_DEFAULT_ACTION: str = settings.SAFETY_DEFAULT_ACTION
SAFETY_CACHE_TTL: int = settings.SAFETY_CACHE_TTL
SAFETY_MAX_CONTENT_LENGTH: int = settings.SAFETY_MAX_CONTENT_LENGTH
SAFETY_LOG_ALL_CHECKS: bool = settings.SAFETY_LOG_ALL_CHECKS

# Enterprise SSO Settings
SSO_ENABLED: bool = settings.SSO_ENABLED
SSO_CACHE_TTL: int = settings.SSO_CACHE_TTL
SSO_SESSION_TIMEOUT: int = settings.SSO_SESSION_TIMEOUT
SSO_ALLOW_MULTIPLE_SESSIONS: bool = settings.SSO_ALLOW_MULTIPLE_SESSIONS

# Status Page Settings
STATUS_ENABLED: bool = settings.STATUS_ENABLED
STATUS_CACHE_TTL: int = settings.STATUS_CACHE_TTL
STATUS_DEFAULT_PAGE_SIZE: int = settings.STATUS_DEFAULT_PAGE_SIZE

# Data Transfer Settings
DATA_TRANSFER_ENABLED: bool = settings.DATA_TRANSFER_ENABLED
DATA_TRANSFER_CACHE_TTL: int = settings.DATA_TRANSFER_CACHE_TTL
DATA_EXPORT_EXPIRY_DAYS: int = settings.DATA_EXPORT_EXPIRY_DAYS
DATA_EXPORT_MAX_RECORDS: int = settings.DATA_EXPORT_MAX_RECORDS
DATA_IMPORT_MAX_FILE_SIZE: int = settings.DATA_IMPORT_MAX_FILE_SIZE

# Backup Status (SOC 2 CC6.5)
BACKUP_STATUS_URL: str | None = settings.BACKUP_STATUS_URL

# SIEM Integration (SOC 2 CC7.2)
SIEM_ENABLED: bool = settings.SIEM_ENABLED
SIEM_WEBHOOK_URL: str | None = settings.SIEM_WEBHOOK_URL
SIEM_BATCH_INTERVAL: int = settings.SIEM_BATCH_INTERVAL

# Feature Flag Settings
FEATURE_FLAG_ENABLED: bool = settings.FEATURE_FLAG_ENABLED
FEATURE_FLAG_CACHE_TTL: int = settings.FEATURE_FLAG_CACHE_TTL
