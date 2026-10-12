import os
import re
from typing import Any

from swx_core.security.encryption import decrypt_value, is_encrypted

ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::(?:-)?([^}]*))?\}")


def _resolve_value(value: str) -> str:
    if not ENV_VAR_PATTERN.search(value):
        return value

    def replace_match(match: re.Match[str]) -> str:
        env_var, default = match.group(1), match.group(2)
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        raise ValueError(f"Required environment variable '{env_var}' is not set")

    return ENV_VAR_PATTERN.sub(replace_match, value)


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    resolved_config: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            resolved_config[key] = _resolve_value(value)
        elif isinstance(value, dict):
            resolved_config[key] = resolve_config(value)
        elif isinstance(value, list):
            resolved_config[key] = [_resolve_value(item) if isinstance(item, str) else item for item in value]
        else:
            resolved_config[key] = value
    return resolved_config


def resolve_api_key(config: dict[str, Any], credential_source: str, encrypted_api_key: str | None = None) -> str:
    """Resolve an API key based on credential source.

    Args:
        config: The provider credentials dict.
        credential_source: One of 'env_placeholder', 'encrypted_db', 'direct'.
        encrypted_api_key: The encrypted API key from DB (used when credential_source='encrypted_db').

    Returns:
        The resolved plaintext API key.
    """
    match credential_source:
        case "encrypted_db":
            if encrypted_api_key and is_encrypted(encrypted_api_key):
                return decrypt_value(encrypted_api_key)
            if encrypted_api_key:
                return encrypted_api_key
            resolved = resolve_config(config)
            return str(resolved.get("api_key", ""))
        case "direct":
            resolved = resolve_config(config)
            return str(resolved.get("api_key", ""))
        case _:
            resolved = resolve_config(config)
            return str(resolved.get("api_key", ""))


def mask_api_key(key: str | None) -> str:
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
