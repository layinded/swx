"""Security module — lazy imports to avoid circular dependency.

Importing `swx_core.security` must not eagerly trigger `password_security`,
which depends on `swx_core.auth` — creating a circular import when the auth
module imports back from `swx_core.security.password_security`.

All symbols remain available via `from swx_core.security import ...`; they
are resolved on first access, not at module load time.
"""

from __future__ import annotations

import importlib as _il


def __getattr__(name: str) -> object:
    _LAZY = {
        "get_password_hash": ".password_security",
        "verify_password": ".password_security",
        "generate_password_reset_token": ".password_security",
        "verify_password_reset_token": ".password_security",
        "create_access_token": ".refresh_token_service",
        "create_refresh_token": ".refresh_token_service",
        "verify_refresh_token": ".refresh_token_service",
        "revoke_refresh_token": ".refresh_token_service",
        "revoke_all_tokens": ".refresh_token_service",
        "EncryptionService": ".encryption",
        "encrypt_value": ".encryption",
        "decrypt_value": ".encryption",
        "encrypt_api_key": ".encryption",
        "decrypt_api_key": ".encryption",
        "is_encrypted": ".encryption",
    }
    if name in _LAZY:
        module = _il.import_module(_LAZY[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_password_hash",
    "verify_password",
    "generate_password_reset_token",
    "verify_password_reset_token",
    "create_access_token",
    "create_refresh_token",
    "verify_refresh_token",
    "revoke_refresh_token",
    "revoke_all_tokens",
    "EncryptionService",
    "encrypt_value",
    "decrypt_value",
    "encrypt_api_key",
    "decrypt_api_key",
    "is_encrypted",
]