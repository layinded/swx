"""
SwX Repositories Package
------------------------
Provides base repository and utilities for data access.
"""

from swx_core.repositories.base import BaseRepository
from swx_core.repositories.tenant_aware import TenantAwareRepository

__all__ = ["BaseRepository", "TenantAwareRepository"]