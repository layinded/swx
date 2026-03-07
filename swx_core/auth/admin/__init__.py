"""
Admin Authentication
--------------------
This module provides authentication for admin domain users.

Admin users are separate from regular users and have their own:
- Authentication endpoints
- Token audience ("admin")
- Permission system
"""

from swx_core.auth.admin.dependencies import (
    get_current_admin_user,
    AdminUserDep,
)

__all__ = [
    "get_current_admin_user",
    "AdminUserDep",
]
