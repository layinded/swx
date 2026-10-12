"""
Configuration value validation utilities.

Provides functions to validate that config values are actual values,
not placeholder strings like <KEY> or ${VAR} that would crash external SDKs.
"""

import re
from typing import cast

PLACEHOLDER_PATTERNS = [
    re.compile(r"^<\w+>$"),
    re.compile(r"^\$\{[^}]+\}$"),
    re.compile(r"^\$\w+$"),
]

MOCK_PREFIXES = (
    "sk_test_mock",
    "whsec_mock",
    "pk_test_mock",
)


def is_valid_config_value(value: str | None) -> bool:
    """Check if a config value is not a placeholder, mock, or empty string."""
    if not isinstance(value, str) or not value:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if any(pattern.match(stripped) for pattern in PLACEHOLDER_PATTERNS):
        return False
    if stripped.startswith(MOCK_PREFIXES):
        return False
    return True


def is_valid_api_key(value: str | None, min_length: int = 8) -> bool:
    """Validate that an API key is not a placeholder and meets minimum length."""
    if not is_valid_config_value(value):
        return False
    validated_value = cast(str, value)
    return len(validated_value) >= min_length


def is_valid_dsn(value: str | None) -> bool:
    """Validate that a DSN value looks like a proper Sentry/monitoring DSN."""
    if not is_valid_config_value(value):
        return False
    validated_value = cast(str, value)
    return validated_value.startswith(("http://", "https://")) and len(validated_value) > 20


def is_valid_redis_url(value: str | None) -> bool:
    """Validate that a Redis URL has proper format."""
    if not is_valid_config_value(value):
        return False
    validated_value = cast(str, value)
    return validated_value.startswith(("redis://", "rediss://", "unix://"))


def is_valid_webhook_secret(value: str | None) -> bool:
    """Validate that a webhook secret is not a mock or placeholder."""
    if not is_valid_config_value(value):
        return False
    validated_value = cast(str, value)
    if validated_value.startswith(("whsec_mock", "whsec_test")):
        return False
    return len(validated_value) >= 8
