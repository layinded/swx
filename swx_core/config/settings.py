"""
Application Settings Configuration
----------------------------------
This module defines the global settings for the SwX-API.

Features:
- Reads environment variables from `.env` file.
- Configures API, database, security, email, and CORS settings.
- Provides dynamic property-based settings.

Configuration Sections:
- API Configuration
- Security & Authentication
- CORS (Cross-Origin Resource Sharing)
- Database Configuration
- Email Settings
- Superuser Defaults
"""

import secrets
from typing import Any, List, Literal
from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings, loaded from environment variables or `.env` file.

    Attributes:
        PROJECT_NAME (str): Name of the project.
        ROUTE_PREFIX (str): Base API route prefix.
        CORE_ROUTE_PREFIX (str): Prefix for core framework routes (e.g., "" for /api/auth or "/v1" for /api/v1/auth).
        API_VERSIONS (List[str]): List of supported API versions.
        DEFAULT_API_VERSION (str): Default API version.
        BACKEND_HOST (str): Backend service host URL.
        FRONTEND_HOST (str): Frontend application URL.
        ENVIRONMENT (Literal): Deployment environment (`local`, `staging`, `production`).
        SECRET_KEY (str): Secret key for signing authentication tokens.
        ACCESS_TOKEN_EXPIRE_MINUTES (int): Expiry duration of access tokens (in minutes).
        REFRESH_TOKEN_EXPIRE_DAYS (int): Expiry duration of refresh tokens (in days).
        BACKEND_CORS_ORIGINS (str | list[str]): Allowed CORS origins.
        DOCKERIZED (bool): Whether the application runs in a Docker container.
        DATABASE_TYPE (Literal): Type of database (`sqlite`, `postgres`, `mysql`).
        DB_HOST (str): Database host address.
        DB_PORT (int): Database connection port.
        DB_USER (str): Database username.
        DB_PASSWORD (str): Database password.
        DB_NAME (str): Database name.
        SMTP settings: SMTP configurations for sending emails.
        FIRST_SUPERUSER (str): Default superuser email.
        FIRST_SUPERUSER_PASSWORD (str): Default superuser password.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # API Configuration
    PROJECT_NAME: str
    ROUTE_PREFIX: str = Field("/api", description="Base API route prefix")
    CORE_ROUTE_PREFIX: str = Field(
        "",
        description="Prefix for core framework routes. Empty string puts core routes at /api/auth. "
        "Set to '/v1' to mount core routes at /api/v1/auth for consistency with app versioned routes.",
    )
    API_VERSIONS: List[str] = Field(["v1", "v2"], description="Supported API versions")
    DEFAULT_API_VERSION: str = Field("v1", description="Default API version")
    STRICT_ROUTE_LOADING: bool = Field(
        False,
        description="If True, raise errors for missing routers instead of warnings",
    )

    BACKEND_HOST: str = Field(
        "http://localhost:8000", description="Backend API host URL"
    )
    FRONTEND_HOST: str = Field(
        "http://localhost:5173", description="Frontend application URL"
    )
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    LOG_LEVEL: Literal[
        "debug", "info", "warning", "error", "critical", "production"
    ] = Field(default="warning")

    LOG_DIR: str = Field(
        default="logs",
        description="Directory for log files (default: 'logs')"
    )

    @field_validator("LOG_LEVEL", mode="before")
    def normalize_log_level(cls, v: Any) -> str:
        """Normalize LOG_LEVEL to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v

    # Security & Authentication
    PASSWORD_SECURITY_ALGORITHM: str = Field(
        default="HS256", description="Algorithm for password security"
    )
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    REFRESH_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for refresh tokens",
    )
    PASSWORD_RESET_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for password reset tokens (separate from access tokens)",
    )

    # CORS Settings
    BACKEND_CORS_ORIGINS: str | list[str] = Field(
        "", description="Allowed CORS origins"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def parse_cors_string(cls, v: Any) -> list[str]:
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
            return v
        raise ValueError(f"Invalid CORS origin format: {v}")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> List[str]:
        """Ensures CORS settings return a valid list."""
        origins = (
            list(self.BACKEND_CORS_ORIGINS)
            if isinstance(self.BACKEND_CORS_ORIGINS, list)
            else [self.BACKEND_CORS_ORIGINS]
        )
        origins.extend([self.FRONTEND_HOST, self.BACKEND_HOST])
        return list(set(origins))

    # Detect Docker Environment
    DOCKERIZED: bool = Field(
        default_factory=lambda: False,
        description="Detects if the app runs inside Docker",
    )

    # Database Configuration
    DATABASE_TYPE: Literal["sqlite", "postgres", "mysql"] = "postgres"
    DB_HOST: str = Field(default="localhost", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_USER: str = "swx_user"
    DB_PASSWORD: str = "changeme"
    DB_NAME: str = "swx_db"

    # Allow overriding the database URI directly
    DATABASE_URL: str | None = Field(
        default=None, description="Override database URL (takes precedence)"
    )
    ASYNC_DATABASE_URL: str | None = Field(
        default=None, description="Override async database URL (takes precedence)"
    )

    @property
    def ASYNC_SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.ASYNC_DATABASE_URL:
            return self.ASYNC_DATABASE_URL

        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("mysql://"):
                return url.replace("mysql://", "mysql+asyncmy://", 1)
            return url

        db_host = self.DB_HOST

        if self.DATABASE_TYPE == "sqlite":
            return f"sqlite+aiosqlite:///./{self.DB_NAME}.db"
        elif self.DATABASE_TYPE == "mysql":
            return f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Generates a dynamic database connection URL.

        Returns:
            str: The full database connection string.
        """
        # Allow direct override
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # Use DB_HOST directly
        db_host = self.DB_HOST

        if self.DATABASE_TYPE == "sqlite":
            return f"sqlite:///./{self.DB_NAME}.db"
        elif self.DATABASE_TYPE == "mysql":
            return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"

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

    # Auth Cache Configuration
    USER_CACHE_ENABLED: bool = Field(
        default=False,
        description="Enable Redis-backed L1/L2 cache for user auth lookups (backward compatible)",
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

    BILLING_ENABLED: bool = Field(
        default=False, description="Enable Stripe billing integration"
    )
    AUTO_ASSIGN_DEFAULT_ROLE: bool = Field(
        default=True,
        description="Automatically assign DEFAULT_USER_ROLE to new users on registration",
    )
    DEFAULT_USER_ROLE: str = Field(
        default="user",
        description="Role name assigned to newly registered users (requires AUTO_ASSIGN_DEFAULT_ROLE=True)",
    )
    DEFAULT_PLAN_KEY: str = Field(
        default="free",
        description="Plan key for new user billing subscriptions (requires BILLING_ENABLED=True)",
    )
    AUTO_CREATE_BILLING_ACCOUNT: bool = Field(
        default=True,
        description="Automatically create a billing account for new users on registration",
    )
    AUTO_CREATE_PERSONAL_TEAM: bool = Field(
        default=True,
        description="Automatically create a personal team and set tenant_id for new users on registration",
    )
    STRIPE_API_KEY: str | None = Field(default=None, description="Stripe API key")
    STRIPE_WEBHOOK_SECRET: str | None = Field(
        default=None, description="Stripe webhook secret"
    )

    MONITORING_ENABLED: bool = Field(
        default=False, description="Enable Sentry monitoring"
    )
    SENTRY_DSN: str | None = Field(
        default=None, description="Sentry DSN for error tracking"
    )

    JOBS_ENABLED: bool = Field(
        default=False, description="Enable Celery background jobs"
    )
    AI_ENABLED: bool = Field(
        default=False, description="Enable AI/vector embeddings (pgai)"
    )

    @property
    def is_billing_available(self) -> bool:
        if not self.BILLING_ENABLED:
            return False
        try:
            import stripe

            return stripe is not None
        except ImportError:
            return False

    @property
    def is_monitoring_available(self) -> bool:
        """Check if monitoring is available (enabled + sentry installed)."""
        if not self.MONITORING_ENABLED:
            return False
        try:
            import sentry_sdk

            return sentry_sdk is not None
        except ImportError:
            return False

    @property
    def is_jobs_available(self) -> bool:
        """Check if jobs is available (enabled + celery installed)."""
        if not self.JOBS_ENABLED:
            return False
        try:
            import celery

            return celery is not None
        except ImportError:
            return False

    @property
    def is_ai_available(self) -> bool:
        """Check if AI is available (enabled + pgai installed)."""
        if not self.AI_ENABLED:
            return False
        try:
            import pgai

            return pgai is not None
        except ImportError:
            return False


# Instantiate settings
settings = Settings()
