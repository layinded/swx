"""
SwX Repositories Package
------------------------
Provides base repository and utilities for data access.
"""

from swx_core.repositories.base import BaseRepository
from swx_core.repositories.tenant_aware import TenantAwareRepository
from swx_core.repositories import conversation_repository
from swx_core.repositories import safety_repository
from swx_core.repositories import sso_repository
from swx_core.repositories import status_repository
from swx_core.repositories import data_transfer_repository
from swx_core.repositories import feature_flag_repository
from swx_core.repositories import mfa_repository
from swx_core.repositories import social_account_repository
from swx_core.repositories import erasure_repository
from swx_core.repositories import gdpr_export_repository

__all__ = [
    "BaseRepository",
    "TenantAwareRepository",
    "conversation_repository",
    "safety_repository",
    "sso_repository",
    "status_repository",
    "data_transfer_repository",
    "feature_flag_repository",
    "mfa_repository",
    "social_account_repository",
    "erasure_repository",
    "gdpr_export_repository",
]