# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Security & Authentication Settings Mixin.

Defines security configuration: token algorithms, secret keys, expiry
durations, MFA, email verification, social account linking, and account
lockout controls.
"""

import secrets

from pydantic import Field
from pydantic_settings import BaseSettings


class SecuritySettingsMixin(BaseSettings):
    """Security and authentication configuration."""

    # Security & Authentication
    PASSWORD_SECURITY_ALGORITHM: str = Field(
        default="HS256", description="Algorithm for password security"
    )
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    MFA_CHALLENGE_EXPIRE_MINUTES: int = 5
    EMAIL_VERIFICATION_ENABLED: bool = True
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    SOCIAL_ACCOUNT_LINKING_ENABLED: bool = True
    REFRESH_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for refresh tokens",
    )
    PASSWORD_RESET_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for password reset tokens (separate from access tokens)",
    )
