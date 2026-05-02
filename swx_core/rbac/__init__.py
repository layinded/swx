"""
RBAC (Role-Based Access Control) Module
----------------------------------------
This module provides permission checking and RBAC helpers.

Exports:
- Permission checking functions
- FastAPI dependencies for permission enforcement
- Role and permission query helpers
"""

from swx_core.rbac.helpers import (
    has_permission,
    has_role,
    get_user_permissions,
    get_user_roles,
    check_team_permission,
)
from swx_core.rbac.dependencies import (
    require_permission,
    require_role,
    require_team_permission,
)

__all__ = [
    # Helpers
    "has_permission",
    "has_role",
    "get_user_permissions",
    "get_user_roles",
    "check_team_permission",
    # Dependencies
    "require_permission",
    "require_role",
    "require_team_permission",
]
