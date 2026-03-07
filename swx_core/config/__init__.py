"""
SwX Configuration Module.

Exports:
    settings: Global settings instance
    discovery: Configurable discovery paths for app modules
"""

from swx_core.config.settings import Settings, settings
from swx_core.config.discovery import DiscoveryConfig, discovery, get_discovery, reset_discovery

__all__ = [
    "Settings",
    "settings",
    "DiscoveryConfig",
    "discovery",
    "get_discovery",
    "reset_discovery",
]