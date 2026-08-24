# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

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
from typing import ClassVar, Literal

from pydantic import AliasChoices, Field, computed_field, field_validator
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

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # API Configuration
    PROJECT_NAME: str = "SwX API"
    ROUTE_PREFIX: str = Field("/api", description="Base API route prefix")
    CORE_ROUTE_PREFIX: str = Field(
        "",
        description=(
            "Prefix for core framework routes. Empty string puts core routes at /api/auth. "
            "Set to '/v1' to mount core routes at /api/v1/auth for consistency with app versioned routes."
        ),
    )
    API_VERSIONS: list[str] = Field(["v1", "v2"], description="Supported API versions")
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
    def normalize_log_level(cls, v: object) -> object:
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

    # Encryption Settings
    SWX_ENCRYPTION_KEY: str | None = Field(
        default=None,
        description="Master encryption key for at-rest field encryption. Required to enable encryption.",
    )
    SWX_ENCRYPTION_KEY_PREVIOUS: str | None = Field(
        default=None,
        description="Previous master key for key rotation. Enables dual-key decryption window.",
    )
    SWX_ENCRYPTION_SALT: str = Field(
        default="swx-default-encryption-salt",
        description="PBKDF2 salt for encryption key derivation. Changing this invalidates all existing encrypted data.",
    )

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

    # Test-Friendly Database Configuration
    TESTING: bool = Field(
        default=False,
        description="Enable test mode: lazy engine init, TEST_DATABASE_URL support, reset_engine()",
    )
    TEST_DATABASE_URL: str | None = Field(
        default=None,
        description="Override DATABASE_URL in test mode (takes precedence over DATABASE_URL)",
    )
    DB_POOL_CLASS: str = Field(
        default="QueuePool",
        description=(
            "SQLAlchemy pool class name: QueuePool (default), NullPool (no pooling, ideal for tests), "
            "SingletonThreadPool (SQLite). Set to NullPool for pytest-asyncio compatibility."
        ),
    )

    # Database Pool Configuration
    DB_POOL_SIZE: int = Field(
        default=20, description="Base connection pool size for async engine"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=10, description="Max overflow connections beyond pool_size for async engine"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30, description="Seconds to wait for a connection from pool before raising"
    )
    DB_POOL_RECYCLE: int = Field(
        default=3600, description="Seconds before recycling a connection (prevents stale connections)"
    )
    DB_POOL_USE_LIFO: bool = Field(
        default=False, description="Use LIFO connection reuse (warmer connections in production)"
    )
    DB_STATEMENT_TIMEOUT_MS: int = Field(
        default=0, description="PostgreSQL statement timeout in milliseconds (0 = disabled)"
    )
    DB_SYNC_POOL_SIZE: int = Field(
        default=5, description="Base connection pool size for sync engine (Celery workers)"
    )
    DB_SYNC_MAX_OVERFLOW: int = Field(
        default=5, description="Max overflow connections beyond sync pool_size"
    )

    # Alembic Configuration
    ALEMBIC_CONFIG_PATH: str = Field(
        default="alembic.ini",
        description=(
            "Path to alembic.ini. Defaults to 'alembic.ini' (CWD-relative). "
            "Set to an absolute path in containers where CWD differs from the "
            "migrations directory, e.g. '/app/alembic.ini'."
        ),
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

    BILLING_ENABLED: bool = Field(
        default=False, description="Enable Stripe billing integration"
    )
    CONSENT_ENABLED: bool = Field(
        default=True, description="Enable consent management framework"
    )
    CONSENT_AUTO_EXPIRE_DAYS: int = Field(
        default=0, description="Auto-expire consents after N days (0 = disabled)"
    )
    LEDGER_ENABLED: bool = Field(
        default=True, description="Enable append-only ledger framework"
    )
    LEDGER_BALANCE_CACHE_TTL: int = Field(
        default=300, description="TTL in seconds for ledger balance cache"
    )
    LEDGER_ALLOW_NEGATIVE_BALANCE: bool = Field(
        default=False, description="Allow balances to go negative"
    )
    LLM_ENABLED: bool = Field(
        default=True, description="Enable database-driven LLM provider routing"
    )
    LLM_DEFAULT_TIMEOUT: int = Field(
        default=60, description="Default timeout in seconds for provider calls"
    )
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = Field(
        default=5, description="Failures before opening an LLM provider circuit"
    )
    LLM_CIRCUIT_BREAKER_RESET_SECONDS: int = Field(
        default=30, description="Seconds before a provider circuit can half-open"
    )
    LLM_MAX_RETRIES: int = Field(
        default=3, description="Maximum retries for resilient provider calls"
    )
    LLM_USAGE_LOG_ENABLED: bool = Field(
        default=True, description="Persist LLM usage logs for cost and latency tracking"
    )
    LLM_STRUCTURED_SSE: bool = Field(
        default=True,
        description="Yield SSEEvent objects from stream() instead of raw strings. Gate for backward compatibility.",
    )
    LLM_DEFAULT_MODELS_OPENAI: list[str] = Field(
        default=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview", "o1-mini"],
        description="Fallback model list for OpenAI when API listing unavailable",
    )
    LLM_DEFAULT_MODELS_AZURE: list[str] = Field(
        default=["gpt-4o", "gpt-4o-mini"],
        description="Fallback model list for Azure OpenAI when API listing unavailable",
    )
    LLM_DEFAULT_MODELS_ANTHROPIC: list[str] = Field(
        default=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
        description="Fallback model list for Anthropic (no model listing API)",
    )
    LLM_DEFAULT_MODELS_OLLAMA: list[str] = Field(
        default=["llama3.2", "mistral", "codellama"],
        description="Fallback model list for Ollama when API listing unavailable",
    )
    SWX_SERVICE_TOKEN: str | None = Field(
        default=None,
        description="Shared secret for service-to-service auth via X-Service-Token header",
        validation_alias=AliasChoices("SWX_SERVICE_TOKEN", "SERVICE_TOKEN", "GATEWAY_SERVICE_TOKEN"),
    )
    SWX_SERVICE_TOKEN_SCOPES: str | None = Field(
        default=None,
        description="Comma-separated permission scopes granted to service principals",
    )
    SWX_AUDIT_RETENTION_DAYS: int | None = Field(
        default=None,
        description="Days to retain audit logs before batch deletion. None or 0 disables retention.",
    )
    SWX_REGIONS: str | None = Field(
        default=None,
        description="JSON mapping of region name → list of country codes for region routing. "
        'Example: \'{"eu": ["DE","FR","NL"], "us": ["US","CA","MX"]}\'',
    )
    SWX_REGION_HEADER: str = Field(
        default="CF-IPCountry",
        description="HTTP header carrying the country code for region routing",
    )
    SWX_AUTH_RATE_LIMIT_RULES: str | None = Field(
        default=None,
        description="JSON array of rate-limit rules for auth endpoints. "
        'Each rule: {"namespace","path_prefix"|"exact_path","methods","max_requests","window_seconds"}',
    )
    ORGANIZATION_ENABLED: bool = Field(
        default=True, description="Enable organization management framework"
    )
    ORGANIZATION_MAX_MEMBERS: int = Field(
        default=0, description="Maximum members allowed per organization (0 = unlimited)"
    )
    ORGANIZATION_INVITATION_EXPIRY_DAYS: int = Field(
        default=7, description="Days before organization invitations expire"
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
    TRIAL_DAYS: int = Field(
        default=30,
        description="Trial duration in days for new accounts (0 disables trial)",
    )
    TRIAL_PLAN_KEY: str = Field(
        default="enterprise",
        description="Plan key whose entitlements are applied during the trial period",
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
    WEBHOOK_ENABLED: bool = Field(default=True, description="Enable outbound webhooks")
    WEBHOOK_DEFAULT_RETRY_COUNT: int = Field(default=3, description="Default outbound webhook retry count")
    WEBHOOK_DEFAULT_RETRY_DELAY: int = Field(default=60, description="Default outbound webhook retry delay seconds")
    WEBHOOK_DEFAULT_TIMEOUT: int = Field(default=30, description="Default outbound webhook timeout seconds")
    WEBHOOK_MAX_RETRIES: int = Field(default=5, description="Maximum outbound webhook retries")
    WEBHOOK_CIRCUIT_BREAKER_THRESHOLD: int = Field(default=5, description="Outbound webhook circuit breaker threshold")
    LOCAL_CURRENCY_ENABLED: bool = True
    PAYSTACK_SECRET_KEY: str = "${PAYSTACK_SECRET_KEY}"
    PAYSTACK_PUBLIC_KEY: str = "${PAYSTACK_PUBLIC_KEY}"
    PAYSTACK_WEBHOOK_SECRET: str = "${PAYSTACK_WEBHOOK_SECRET}"
    FLUTTERWAVE_SECRET_KEY: str = "${FLUTTERWAVE_SECRET_KEY}"
    FLUTTERWAVE_PUBLIC_KEY: str = "${FLUTTERWAVE_PUBLIC_KEY}"
    FLUTTERWAVE_ENCRYPTION_KEY: str = "${FLUTTERWAVE_ENCRYPTION_KEY}"
    FLUTTERWAVE_WEBHOOK_SECRET: str = "${FLUTTERWAVE_WEBHOOK_SECRET}"
    MPESA_CONSUMER_KEY: str = "${MPESA_CONSUMER_KEY}"
    MPESA_CONSUMER_SECRET: str = "${MPESA_CONSUMER_SECRET}"
    MPESA_PASSKEY: str = "${MPESA_PASSKEY}"
    MPESA_SHORTCODE: str = "${MPESA_SHORTCODE}"
    MPESA_ENV: str = "sandbox"
    EXCHANGE_RATE_SYNC_INTERVAL_HOURS: int = 6
    DEFAULT_TAX_JURISDICTION: str = "NG"
    DEFAULT_BASE_CURRENCY: str = "USD"

    QUOTA_WINDOW_HOURS: int = Field(default=5, description="Rolling usage window size in hours")
    QUOTA_WINDOW_DEFAULT_TOKENS: int = Field(default=100_000, description="Default token quota per window")
    QUOTA_MONTHLY_DEFAULT_TOKENS: int = Field(default=1_000_000, description="Default monthly token quota")
    QUOTA_WINDOW_MAX_RESETS: int = Field(default=1, description="Max window resets per window")
    QUOTA_DAILY_MAX_RESETS: int = Field(default=3, description="Max window resets per day")

    USAGE_METERING_DEFAULT_CURRENCY: str = Field(
        default="NGN", description="Default currency for usage metering wallet debits"
    )
    USAGE_METERING_DEFAULT_MODEL_KEY: str = Field(
        default="default", description="Fallback model key when model is not in pricing table"
    )
    USAGE_METERING_MODEL_PRICING: dict = Field(
        default_factory=lambda: {
            "gpt-4": {"input": 30_000, "output": 60_000},
            "gpt-4o": {"input": 2_500, "output": 10_000},
            "gpt-3.5-turbo": {"input": 500, "output": 1_500},
            "claude-3-opus": {"input": 15_000, "output": 75_000},
            "claude-3-sonnet": {"input": 3_000, "output": 15_000},
            "claude-3-haiku": {"input": 250, "output": 1_250},
            "default": {"input": 1_000, "output": 3_000},
        },
        description="Per-model nano pricing for usage metering (input/output per token)",
    )

    QUOTA_MONTHLY_TTL_DAYS: int = Field(default=32, description="TTL in days for monthly quota Redis keys")
    QUOTA_DAILY_TTL_HOURS: int = Field(default=36, description="TTL in hours for daily reset counter Redis keys")
    QUOTA_WINDOW_TTL_BUFFER_HOURS: int = Field(default=1, description="Extra hours added to window key TTL as buffer")
    WEBHOOK_IDEMPOTENCY_TTL: int = Field(default=604800, description="TTL in seconds for webhook idempotency Redis keys (default: 7 days)")
    WEBHOOK_RETENTION_DAYS: int = Field(default=30, description="Days to retain inbound webhook delivery records")

    SWX_AUDIT_RETENTION_POLICIES: dict = Field(
        default_factory=lambda: {
            "auth": 90,
            "billing": 365,
            "admin": 180,
            "gateway": 30,
            "pii": 2555,
            "usage": 90,
        },
        description="Per-log-type retention days (hot DB retention).",
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
    NOTIFICATION_TEMPLATE_DIR: str = Field(default="templates", description="Directory containing file-based notification templates")
    NOTIFICATION_CELERY_TASK_PATH: str = Field(default="swx_core.services.notifications.tasks.send_notification_task", description="Celery task path for queued notification delivery")
    NOTIFICATION_BRAND_COLOR: str = Field(default="#3c42b6", description="Default brand color for notification templates")
    NOTIFICATION_SUPPORT_EMAIL: str = Field(default="support@example.com", description="Support email injected into notification templates")
    AI_ENABLED: bool = Field(
        default=False, description="Enable AI/vector embeddings (pgai)"
    )

    CONVERSATION_ENABLED: bool = Field(default=True, description="Enable conversation state tracking")
    CONVERSATION_DEFAULT_PAGE_SIZE: int = Field(default=50, description="Default page size for conversation listing")
    CONVERSATION_MAX_MESSAGE_LENGTH: int = Field(default=10000, description="Maximum message content length in characters")
    CONVERSATION_CACHE_TTL: int = Field(default=30, description="Conversation config cache TTL in seconds")

    # AI Safety & Content Filtering
    SAFETY_ENABLED: bool = Field(default=True, description="Enable AI safety and content filtering")
    SAFETY_DEFAULT_ACTION: str = Field(default="flag", description="Default action when content is flagged (allow, flag, block, replace)")
    SAFETY_CACHE_TTL: int = Field(default=60, description="Safety filter config cache TTL in seconds")
    SAFETY_MAX_CONTENT_LENGTH: int = Field(default=50000, description="Maximum content length for safety checks in characters")
    SAFETY_LOG_ALL_CHECKS: bool = Field(default=True, description="Log all safety checks for audit trail")

    # Enterprise SSO
    SSO_ENABLED: bool = Field(default=True, description="Enable enterprise SSO (SAML/OIDC)")
    SSO_CACHE_TTL: int = Field(default=60, description="SSO provider config cache TTL in seconds")
    SSO_SESSION_TIMEOUT: int = Field(default=28800, description="SSO session timeout in seconds (default 8 hours)")
    SSO_ALLOW_MULTIPLE_SESSIONS: bool = Field(default=True, description="Allow users to have multiple active SSO sessions")

    # Status Page
    STATUS_ENABLED: bool = Field(default=True, description="Enable status page and incident tracking")
    STATUS_CACHE_TTL: int = Field(default=30, description="Status page cache TTL in seconds")
    STATUS_DEFAULT_PAGE_SIZE: int = Field(default=50, description="Default page size for status listings")

    # Data Export/Import
    DATA_TRANSFER_ENABLED: bool = Field(default=True, description="Enable data export and import")
    DATA_TRANSFER_CACHE_TTL: int = Field(default=60, description="Data transfer config cache TTL in seconds")
    DATA_EXPORT_EXPIRY_DAYS: int = Field(default=7, description="Number of days before export files expire")
    DATA_EXPORT_MAX_RECORDS: int = Field(default=100000, description="Maximum records per export")
    DATA_IMPORT_MAX_FILE_SIZE: int = Field(default=52428800, description="Maximum import file size in bytes (50MB)")

    # Feature Flags & A/B Testing
    FEATURE_FLAG_ENABLED: bool = Field(default=True, description="Enable feature flags and A/B testing")

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
            import celery  # pyright: ignore[reportMissingTypeStubs]

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
settings = Settings()  # pyright: ignore[reportCallIssue]

# Compliance Audit Settings
COMPLIANCE_ENABLED: bool = True
COMPLIANCE_DEFAULT_SEVERITY: str = "info"
COMPLIANCE_DEFAULT_DATA_CLASSIFICATION: str = "PUBLIC"
COMPLIANCE_DEFAULT_IP_MASKING: str = "partial"  # full | partial | none
COMPLIANCE_DEFAULT_RETENTION_DAYS: int = 365
COMPLIANCE_AUTO_MASK_IP: bool = True
COMPLIANCE_AUTO_REDACT_FIELDS: bool = True
COMPLIANCE_DATA_SUBJECT_REQUEST_EXPIRY_DAYS: int = 30

# GDPR Settings
GDPR_ENABLED: bool = True
GDPR_DELETION_GRACE_DAYS: int = 30
GDPR_EXPORT_FORMAT: str = "json"
GDPR_ANONYMIZE_ON_DELETE: bool = True
GDPR_SOLE_OWNER_BLOCK: bool = True
GDPR_EXPORT_EXPIRY_DAYS: int = 7
GDPR_MIN_VERIFICATION_DAYS: int = 1

# Notification Settings
NOTIFICATION_ENABLED: bool = True
NOTIFICATION_DEFAULT_FROM_EMAIL: str = "noreply@example.com"
NOTIFICATION_DEFAULT_FROM_NAME: str = "SwX App"
NOTIFICATION_DEFAULT_RETRY_COUNT: int = 3
NOTIFICATION_DEFAULT_TIMEOUT: int = 30
NOTIFICATION_PROVIDER_CACHE_TTL: int = 30
NOTIFICATION_TEMPLATE_CACHE_TTL: int = 30
NOTIFICATION_RATE_LIMIT_DAILY: int = 100
NOTIFICATION_RATE_LIMIT_HOURLY: int = 20
NOTIFICATION_TEMPLATE_DIR: str = settings.NOTIFICATION_TEMPLATE_DIR
NOTIFICATION_CELERY_TASK_PATH: str = settings.NOTIFICATION_CELERY_TASK_PATH

# API Key Scoping Settings
API_KEY_ENABLED: bool = True
API_KEY_DEFAULT_EXPIRY_DAYS: int = 90
API_KEY_ROTATION_GRACE_HOURS: int = 24
API_KEY_DEFAULT_RATE_LIMIT: int = 60
API_KEY_CACHE_TTL: int = 300

# Webhook Settings
WEBHOOK_ENABLED: bool = settings.WEBHOOK_ENABLED
WEBHOOK_DEFAULT_RETRY_COUNT: int = settings.WEBHOOK_DEFAULT_RETRY_COUNT
WEBHOOK_DEFAULT_RETRY_DELAY: int = settings.WEBHOOK_DEFAULT_RETRY_DELAY
WEBHOOK_DEFAULT_TIMEOUT: int = settings.WEBHOOK_DEFAULT_TIMEOUT
WEBHOOK_MAX_RETRIES: int = settings.WEBHOOK_MAX_RETRIES
WEBHOOK_CIRCUIT_BREAKER_THRESHOLD: int = settings.WEBHOOK_CIRCUIT_BREAKER_THRESHOLD

# Conversation State Settings
CONVERSATION_ENABLED: bool = settings.CONVERSATION_ENABLED
CONVERSATION_DEFAULT_PAGE_SIZE: int = settings.CONVERSATION_DEFAULT_PAGE_SIZE
CONVERSATION_MAX_MESSAGE_LENGTH: int = settings.CONVERSATION_MAX_MESSAGE_LENGTH
CONVERSATION_CACHE_TTL: int = settings.CONVERSATION_CACHE_TTL

# AI Safety Settings
SAFETY_ENABLED: bool = settings.SAFETY_ENABLED
SAFETY_DEFAULT_ACTION: str = settings.SAFETY_DEFAULT_ACTION
SAFETY_CACHE_TTL: int = settings.SAFETY_CACHE_TTL
SAFETY_MAX_CONTENT_LENGTH: int = settings.SAFETY_MAX_CONTENT_LENGTH
SAFETY_LOG_ALL_CHECKS: bool = settings.SAFETY_LOG_ALL_CHECKS

# Enterprise SSO Settings
SSO_ENABLED: bool = settings.SSO_ENABLED
SSO_CACHE_TTL: int = settings.SSO_CACHE_TTL
SSO_SESSION_TIMEOUT: int = settings.SSO_SESSION_TIMEOUT
SSO_ALLOW_MULTIPLE_SESSIONS: bool = settings.SSO_ALLOW_MULTIPLE_SESSIONS

# Status Page Settings
STATUS_ENABLED: bool = settings.STATUS_ENABLED
STATUS_CACHE_TTL: int = settings.STATUS_CACHE_TTL
STATUS_DEFAULT_PAGE_SIZE: int = settings.STATUS_DEFAULT_PAGE_SIZE

# Data Transfer Settings
DATA_TRANSFER_ENABLED: bool = settings.DATA_TRANSFER_ENABLED
DATA_TRANSFER_CACHE_TTL: int = settings.DATA_TRANSFER_CACHE_TTL
DATA_EXPORT_EXPIRY_DAYS: int = settings.DATA_EXPORT_EXPIRY_DAYS
DATA_EXPORT_MAX_RECORDS: int = settings.DATA_EXPORT_MAX_RECORDS
DATA_IMPORT_MAX_FILE_SIZE: int = settings.DATA_IMPORT_MAX_FILE_SIZE

# Feature Flag Settings
FEATURE_FLAG_ENABLED: bool = settings.FEATURE_FLAG_ENABLED
FEATURE_FLAG_CACHE_TTL: int = settings.FEATURE_FLAG_CACHE_TTL
