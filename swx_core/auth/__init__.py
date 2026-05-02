"""
Authentication Module
--------------------
This module provides authentication for different domains:
- System: Internal system users, CLI, background jobs
- Admin: Admin users with admin-only access
- User: Regular application users with team-based access

Each domain has separate authentication flows and token audiences.
"""

from swx_core.auth.user import get_current_user, UserDep
from swx_core.auth.admin import get_current_admin_user, AdminUserDep

__all__ = [
    "get_current_user",
    "UserDep",
    "get_current_admin_user",
    "AdminUserDep",
]
