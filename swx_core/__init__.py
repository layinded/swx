"""
SwX Core Framework
------------------
A production-ready FastAPI framework with RBAC, OAuth, JWT, and modular structure.

This is the reusable framework code. Application-specific code should be in swx_app/.

Usage:
    from swx_core import __version__, get_version_info
    print(__version__)  # "2.0.0"
"""

from swx_core.version import (
    __version__,
    VERSION,
    get_version,
    get_version_info,
    get_major_minor_version,
    is_prerelease,
    check_version_compatible,
)

# Core exports
from swx_core.container import Container, get_container, set_container
from swx_core.guards import JWTGuard, APIKeyGuard, GuardManager
from swx_core.events import EventBus
from swx_core.bootstrap import bootstrap

__all__ = [
    # Version
    "__version__",
    "VERSION",
    "get_version",
    "get_version_info",
    "get_major_minor_version",
    "is_prerelease",
    "check_version_compatible",
    # Container
    "Container",
    "get_container",
    "set_container",
    # Guards
    "JWTGuard",
    "APIKeyGuard",
    "GuardManager",
    # Events
    "EventBus",
    # Bootstrap
    "bootstrap",
]