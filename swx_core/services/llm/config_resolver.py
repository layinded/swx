import os
import re
from typing import Any

ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _substitute(value: str, replacement: str) -> str:
    return ENV_VAR_PATTERN.sub(lambda _: replacement, value)


def _resolve_value(value: str) -> str:
    match = ENV_VAR_PATTERN.search(value)
    if not match:
        return value
    env_var, default = match.group(1), match.group(2)
    env_value = os.environ.get(env_var)
    if env_value is not None:
        return _substitute(value, env_value)
    if default is not None:
        return _substitute(value, default)
    raise ValueError(f"Required environment variable '{env_var}' is not set")


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            resolved[key] = _resolve_value(value)
        elif isinstance(value, dict):
            resolved[key] = resolve_config(value)
        elif isinstance(value, list):
            resolved[key] = [_resolve_value(item) if isinstance(item, str) else item for item in value]
        else:
            resolved[key] = value
    return resolved


def mask_api_key(key: str | None) -> str:
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
