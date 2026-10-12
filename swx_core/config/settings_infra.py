# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Infrastructure Settings Mixin.

Defines infrastructure configuration: CORS, Docker detection, email/SMTP,
superuser defaults, Redis, cookies, rate limiting, security headers, CSRF,
and caching layers (auth, feature flag, settings).
"""

from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings


class InfraSettingsMixin(BaseSettings):
    """Infrastructure and cross-cutting configuration."""

    # CORS Settings
    BACKEND_CORS_ORIGINS: str | list[str] = Field(
        "", description="Allowed CORS origins"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def parse_cors_string(cls, v: object) -> list[str]:
        """
        Parses a comma-separated string into a list of CORS origins.

        Args:
            v (Any): Input value from environment.

        Returns:
            list[str]: A list of CORS origins.

        Raises:
            ValueError: If the format is invalid.
        """
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return [str(i) for i in v]
        raise ValueError(f"Invalid CORS origin format: {v}")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """Ensures CORS settings return a valid list."""
        origins: list[str] = (
            list(self.BACKEND_CORS_ORIGINS)
            if isinstance(self.BACKEND_CORS_ORIGINS, list)
            else [self.BACKEND_CORS_ORIGINS]
        )
        origins.extend([self.FRONTEND_HOST, self.BACKEND_HOST])
        return sorted(set(origins))

    # Detect Docker Environment
    DOCKERIZED: bool = Field(
        default_factory=lambda: False,
        description="Detects if the app runs inside Docker",
    )

    # Email Configuration
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str | None = None
    EMAILS_FROM_NAME: str | None = None
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48
    OTP_LENGTH: int = Field(default=6, description="Email OTP code length")
    OTP_EXPIRY_MINUTES: int = Field(default=10, description="Email OTP expiry in minutes")
    OTP_MAX_ATTEMPTS: int = Field(default=3, description="Maximum OTP verification attempts")
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(default=60, description="OTP resend cooldown in seconds")
    OTP_BYPASS_FOR_TESTING: bool = Field(default=False, description="Return a fixed OTP in local testing mode")
    OTP_BYPASS_EMAILS: str = Field(default="", description="Comma-separated email whitelist for OTP bypass (empty = all emails bypass when OTP_BYPASS_FOR_TESTING is True)")
    TRUSTED_PROXIES: str = Field(default="", description="Comma-separated list of trusted proxy IPs for X-Forwarded-For parsing")

    @property
    def emails_enabled(self) -> bool:
        """
        Determines if email sending is enabled.

        Returns:
            bool: True if email configuration is set correctly, otherwise False.
        """
        return all(
            [self.SMTP_HOST, self.SMTP_USER, self.SMTP_PASSWORD, self.EMAILS_FROM_EMAIL]
        )

    # Superuser Configuration
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "securepassword"

    @property
    def FIRST_ADMIN_EMAIL(self) -> str:
        """Backward compatibility alias for FIRST_SUPERUSER."""
        return self.FIRST_SUPERUSER

    # Redis Configuration (for rate limiting and caching)
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_PASSWORD: str | None = Field(default=None, description="Redis password")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_ENABLED: bool = Field(
        default=True, description="Enable Redis (disable for development without Redis)"
    )

    # Direct REDIS_URL env var support (takes precedence over components)
    REDIS_URL: str | None = Field(
        default=None,
        description="Full Redis URL (takes precedence over REDIS_HOST/PORT/DB)",
    )

    @property
    def redis_url(self) -> str:
        """Get Redis URL, respecting REDIS_URL env var precedence."""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Cookie Settings for OAuth BFF Pattern
    COOKIE_ACCESS_TOKEN_NAME: str = Field(
        default="swx_access_token",
        description="Name of the HTTP-only cookie for access tokens"
    )
    COOKIE_REFRESH_TOKEN_NAME: str = Field(
        default="swx_refresh_token",
        description="Name of the HTTP-only cookie for refresh tokens"
    )
    COOKIE_SECURE: bool = Field(
        default=True,
        description="Set Secure flag on cookies (True in production, False for local dev)"
    )
    COOKIE_SAMESITE: Literal["strict", "lax", "none"] = Field(
        default="lax",
        description="SameSite attribute for cookies (strict, lax, or none)"
    )
    COOKIE_DOMAIN: str | None = Field(
        default=None,
        description="Cookie domain for subdomain sharing (e.g., '.example.com')",
    )

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable rate limiting for authentication endpoints",
    )
    RATE_LIMIT_LOGIN_MAX: int = Field(
        default=5,
        description="Maximum login attempts per minute per IP",
    )
    RATE_LIMIT_REGISTER_MAX: int = Field(
        default=3,
        description="Maximum registration attempts per hour per IP",
    )
    RATE_LIMIT_PASSWORD_RECOVER_MAX: int = Field(
        default=3,
        description="Maximum password recovery attempts per hour per IP",
    )
    RATE_LIMIT_COOKIE_AUTH_MAX: int = Field(
        default=5,
        description="Maximum cookie auth attempts per minute per IP",
    )
    RATE_LIMIT_SKIP_PATHS: list[str] = Field(
        default=[],
        description="Additional paths to skip rate limiting (appended to built-in defaults)",
    )
    RATE_LIMIT_FAIL_OPEN: bool = Field(
        default=False,
        description="Allow requests through when Redis is unavailable (True for dev, False for prod)",
    )
    RATE_LIMIT_OVERRIDE_ENABLED: bool = Field(
        default=True,
        description="Enable database-driven rate limit overrides via SystemConfig (RATE_LIMIT category)",
    )

    # Security Headers (SOC 2 CC7.1)
    SECURITY_HEADERS_ENABLED: bool = Field(
        default=True,
        description="Enable security headers middleware (X-Content-Type-Options, CSP, HSTS, etc.)",
    )

    # Account Lockout (SOC 2 CC6.1)
    ACCOUNT_LOCKOUT_THRESHOLD: int = Field(
        default=5,
        description="Number of failed login attempts before account lockout (0 disables lockout)",
    )
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = Field(
        default=30,
        description="Duration in minutes to lock an account after exceeding the threshold",
    )

    # Password Reset Rate Limiting (SOC 2 CC6.1)
    PASSWORD_RESET_RATE_LIMIT: int = Field(
        default=3,
        description="Maximum password reset requests per email per hour (0 disables rate limiting)",
    )

    # CSRF Protection Configuration
    CSRF_ENABLED: bool = Field(
        default=True,
        description="Enable CSRF protection for cookie-based auth",
    )
    CSRF_TOKEN_LENGTH: int = Field(
        default=32,
        description="Length of CSRF tokens (bytes)",
    )
    CSRF_COOKIE_NAME: str = Field(
        default="csrf_token",
        description="Name of CSRF cookie",
    )
    CSRF_HEADER_NAME: str = Field(
        default="X-CSRF-Token",
        description="Name of CSRF header",
    )
    CSRF_COOKIE_MAX_AGE: int = Field(
        default=86400,  # 24 hours
        description="CSRF cookie maximum age in seconds",
    )
    CSRF_LOGIN_PATHS: list[str] = Field(
        default=["/api/auth/login", "/api/auth/social/login"],
        description="Paths that trigger CSRF cookie creation",
    )
    CSRF_LOGOUT_PATHS: list[str] = Field(
        default=["/api/auth/logout"],
        description="Paths that trigger CSRF cookie deletion",
    )
    CSRF_REFRESH_PATHS: list[str] = Field(
        default=["/api/auth/refresh"],
        description="Paths that refresh CSRF cookie",
    )

    # Auth Cache Configuration
    USER_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable Redis-backed L1/L2 cache for user auth lookups (requires Redis)",
    )
    USER_CACHE_TTL: int = Field(
        default=300,
        description="TTL in seconds for cached user profiles (default: 5 min)",
    )
    USER_PERMISSIONS_CACHE_TTL: int = Field(
        default=120,
        description="TTL in seconds for cached user permissions (default: 2 min)",
    )
    USER_CACHE_L1_MAX_ENTRIES: int = Field(
        default=1000,
        description="Maximum entries in process-local L1 cache",
    )
    ADMIN_CACHE_ENABLED: bool = Field(
        default=False,
        description="Enable Redis-backed L1/L2 cache for admin auth lookups (backward compatible)",
    )
    ADMIN_CACHE_TTL: int = Field(
        default=300,
        description="TTL in seconds for cached admin profiles (default: 5 min)",
    )

    # Feature Flag Cache Configuration
    FEATURE_FLAG_CACHE_ENABLED: bool = Field(
        default=False,
        description="Enable Redis-backed L1/L2 cache for feature flag lookups (backward compatible)",
    )
    FEATURE_FLAG_CACHE_TTL: int = Field(
        default=300,
        description="TTL in seconds for cached feature flags (default: 5 min)",
    )
    FEATURE_FLAG_CACHE_L1_MAX_ENTRIES: int = Field(
        default=200,
        description="Maximum entries in process-local L1 cache for feature flags",
    )

    # Settings Cache Configuration
    SETTINGS_CACHE_ENABLED: bool = Field(
        default=False,
        description="Enable Redis-backed L1/L2 cache for runtime settings lookups (backward compatible)",
    )
    SETTINGS_CACHE_TTL: int = Field(
        default=60,
        description="TTL in seconds for cached runtime settings (default: 1 min)",
    )
    SETTINGS_CACHE_L1_MAX_ENTRIES: int = Field(
        default=500,
        description="Maximum entries in process-local L1 cache for settings",
    )

    # Event Bridge Configuration (Redis Pub/Sub)
    EVENT_BRIDGE_ENABLED: bool = Field(
        default=True,
        description="Enable cross-worker event broadcasting via Redis Pub/Sub (requires REDIS_ENABLED)",
    )
    EVENT_BRIDGE_CHANNEL_PREFIX: str = Field(
        default="swx:events",
        description="Redis channel prefix for event broadcasting (default: 'swx:events')",
    )
