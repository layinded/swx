import os
import re
from typing import Any

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


def mask_api_key(key: str | None) -> str:
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
