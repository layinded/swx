"""
User Authentication
-------------------
This module provides authentication for user domain (regular application users).

Users authenticate separately from admin users and use tokens with audience="user".
Users belong to teams and have team-scoped roles and permissions.

Supports both:
- Authorization: Bearer header (for API clients)
- httpOnly cookie (for browser-based apps using BFF pattern)
"""

from swx_core.auth.user.dependencies import (
    get_current_user,
    UserDep,
    UserTokenDep,
)
from swx_core.auth.core.bearer_or_cookie import BearerOrCookieAuth, OptionalBearerOrCookieAuth

__all__ = [
    "get_current_user",
    "UserDep",
    "UserTokenDep",
    "BearerOrCookieAuth",
    "OptionalBearerOrCookieAuth",
]
