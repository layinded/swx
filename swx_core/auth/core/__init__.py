"""
Core Authentication Utilities
-----------------------------
This module provides shared authentication utilities used by all domains.
"""

from swx_core.auth.core.jwt import (
    create_token,
    decode_token,
    TokenAudience,
)

__all__ = [
    "create_token",
    "decode_token",
    "TokenAudience",
]
