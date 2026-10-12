"""
SwX Core Framework
===================

Production-ready FastAPI framework with RBAC, OAuth, JWT, and modular structure.

This package provides:
- Base controllers, services, and repositories
- Authentication and authorization (JWT, OAuth, API keys)
- Rate limiting and caching
- Event-driven architecture
- Background job processing
- Billing integration
- Comprehensive utilities

Usage:
    from swx_core import __version__, get_version_info
    print(__version__)  # "2.1.6"
    
    # Base classes
    from swx_core.controllers import BaseController
    from swx_core.services import BaseService
    from swx_core.repositories import BaseRepository
    
    # Utilities
    from swx_core.utils import PaginatedResponse, APIResponse
    
    # Models
    from swx_core.models import User, Role, Permission
"""

# Version
from swx_core.version import (
    __version__,
    VERSION,
    get_version,
    get_version_info,
    get_major_minor_version,
    is_prerelease,
    check_version_compatible,
)

# Container
from swx_core.container import Container, get_container, set_container

# Guards
from swx_core.guards import JWTGuard, APIKeyGuard, GuardManager

# Events
from swx_core.events import EventBus

# Bootstrap
from swx_core.bootstrap import bootstrap

# Application factory
from swx_core.app_factory import create_swx_app

# Lifecycle
from swx_core.lifecycle import LifecycleManager, LifecycleService, LifecycleError

# Background scheduler
from swx_core.background import BackgroundScheduler

# Production validator
from swx_core.config.validator import ProductionValidator

# Base classes
from swx_core.controllers import BaseController
from swx_core.services import BaseService
from swx_core.repositories import BaseRepository

# Models
from swx_core.models import Base

# Utils
from swx_core.utils import (
    # Pagination
    PaginationParams,
    PaginatedResponse,
    # Response
    APIResponse,
    DataResponse,
    ErrorResponse,
    # Cache
    get_cache,
    set_cache,
    cached,
    # Mixins
    TimestampMixin,
    SoftDeleteMixin,
    UUIDPrimaryKeyMixin,
    ActiveMixin,
    FullModelMixin,
)

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
    
    # Application factory
    "create_swx_app",
    
    # Lifecycle
    "LifecycleManager",
    "LifecycleService",
    "LifecycleError",
    
    # Background scheduler
    "BackgroundScheduler",
    
    # Production validator
    "ProductionValidator",
    
    # Base classes
    "BaseController",
    "BaseService",
    "BaseRepository",
    
    # Models
    "Base",
    
    # Pagination
    "PaginationParams",
    "PaginatedResponse",
    
    # Response
    "APIResponse",
    "DataResponse",
    "ErrorResponse",
    
    # Cache
    "get_cache",
    "set_cache",
    "cached",
    
    # Mixins
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDPrimaryKeyMixin",
    "ActiveMixin",
    "FullModelMixin",
]