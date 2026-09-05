"""
SwX Production Configuration Validator
---------------------------------------
Extensible mechanism for applications to declare production requirements.

Applications register validation rules (required secrets, forbidden
localhost URLs, incompatible settings) and call ``validate()`` at startup.
Invalid configuration fails fast with actionable error messages.

Usage::

    from swx_core.config.validator import ProductionValidator

    validator = ProductionValidator()
    validator.require("STRIPE_API_KEY")
    validator.require("DEVICE_ENROLLMENT_SECRET")
    validator.forbid_localhost("DOWNLOAD_BASE_URL")
    validator.check(
        lambda: settings.BILLING_ENABLED or not settings.STRIPE_API_KEY,
        "STRIPE_API_KEY is set but billing is disabled",
    )

    errors = validator.validate(environment=settings.ENVIRONMENT)
    if errors:
        for error in errors:
            print(f"  ✗ {error}")
        raise SystemExit(1)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable


# Patterns that indicate placeholder/unset values.
_PLACEHOLDER_PATTERNS = re.compile(
    r"^(<[^>]+>|\$\{[^}]+\}|\$[A-Z_]+$|sk_test_mock|pk_test_mock|whsec_mock)",
)


@dataclass
class ValidationRule:
    """A single production configuration rule."""

    rule_type: str  # "require" | "forbid_localhost" | "check"
    key: str  # env var name or descriptive label
    message: str = ""
    check_fn: Callable[[], bool] | None = None


class ProductionValidator:
    """Collect and run production configuration rules.

    Call ``validate()`` at startup (before the app accepts traffic).
    In non-production environments, validation is a no-op by default.
    """

    def __init__(self) -> None:
        self._rules: list[ValidationRule] = []

    # -- rule builders (chainable) ------------------------------------

    def require(self, env_var: str, message: str = "") -> "ProductionValidator":
        """Fail if ``env_var`` is missing, empty, or a placeholder.

        Placeholder patterns: ``<KEY>``, ``${VAR}``, ``$VAR``,
        ``sk_test_mock*``, ``pk_test_mock*``, ``whsec_mock*``.
        """
        self._rules.append(
            ValidationRule(
                rule_type="require",
                key=env_var,
                message=message or f"Required environment variable {env_var} is missing or unset",
            )
        )
        return self

    def forbid_localhost(self, env_var: str, message: str = "") -> "ProductionValidator":
        """Fail if ``env_var`` contains ``localhost`` or ``127.0.0.1``."""
        self._rules.append(
            ValidationRule(
                rule_type="forbid_localhost",
                key=env_var,
                message=message or f"{env_var} must not point to localhost in production",
            )
        )
        return self

    def check(self, condition: Callable[[], bool], message: str) -> "ProductionValidator":
        """Fail if ``condition()`` returns ``False``."""
        self._rules.append(
            ValidationRule(
                rule_type="check",
                key=message,
                message=message,
                check_fn=condition,
            )
        )
        return self

    # -- validation ----------------------------------------------------

    def validate(self, environment: str = "production") -> list[str]:
        """Run all rules. Returns a list of error strings (empty = valid).

        By default, validation only runs in ``"production"`` environment.
        Pass ``environment="local"`` or ``"staging"`` to skip checks.
        """
        if environment not in ("production", "prod"):
            return []

        errors: list[str] = []
        for rule in self._rules:
            if rule.rule_type == "require":
                if not self._is_valid_value(os.environ.get(rule.key, "")):
                    errors.append(rule.message)
            elif rule.rule_type == "forbid_localhost":
                value = os.environ.get(rule.key, "")
                if self._is_localhost(value):
                    errors.append(rule.message)
            elif rule.rule_type == "check":
                if rule.check_fn is not None and not rule.check_fn():
                    errors.append(rule.message)

        return errors

    # -- internal ------------------------------------------------------

    @staticmethod
    def _is_valid_value(value: str) -> bool:
        """Return ``False`` if the value is empty or a placeholder."""
        if not value or not value.strip():
            return False
        return not bool(_PLACEHOLDER_PATTERNS.match(value))

    @staticmethod
    def _is_localhost(value: str) -> bool:
        """Return ``True`` if the URL points to localhost or 127.0.0.1."""
        if not value:
            return False
        return "localhost" in value or "127.0.0.1" in value or "0.0.0.0" in value