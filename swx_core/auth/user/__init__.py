"""
User Authentication
-------------------
This module provides authentication for user domain (regular application users).

Users authenticate separately from admin users and use tokens with audience="user".
Users belong to teams and have team-scoped roles and permissions.
"""

from swx_core.auth.user.dependencies import (
    get_current_user,
    UserDep,
)

__all__ = [
    "get_current_user",
    "UserDep",
]
