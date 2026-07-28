"""
SwX Configuration Module.

Exports:
    settings: Global settings instance
    discovery: Configurable discovery paths for app modules
"""

from swx_core.config.settings import Settings, settings
from swx_core.config.discovery import DiscoveryConfig, discovery, get_discovery, reset_discovery
from swx_core.config.validation import (
    is_valid_config_value,
    is_valid_api_key,
    is_valid_dsn,
    is_valid_redis_url,
    is_valid_webhook_secret,
)

__all__ = [
    "Settings",
    "settings",
    "DiscoveryConfig",
    "discovery",
    "get_discovery",
    "reset_discovery",
    "is_valid_config_value",
    "is_valid_api_key",
    "is_valid_dsn",
    "is_valid_redis_url",
    "is_valid_webhook_secret",
]