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
    API_VERSIONS: List[str] = Field(["v1", "v2"], description="Supported API versions")
    DEFAULT_API_VERSION: str = Field("v1", description="Default API version")

    BACKEND_HOST: str = Field("http://localhost:8000", description="Backend API host URL")
    FRONTEND_HOST: str = Field("http://localhost:5173", description="Frontend application URL")
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    LOG_LEVEL: Literal["debug", "info", "warning", "error", "critical", "production"] = Field(default="warning")
    
    @field_validator("LOG_LEVEL", mode="before")
    def normalize_log_level(cls, v: Any) -> str:
        """Normalize LOG_LEVEL to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v

    # Security & Authentication
    PASSWORD_SECURITY_ALGORITHM: str = Field(default="HS256", description="Algorithm for password security")
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32), description="Secret key for JWT tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    REFRESH_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32),
                                    description="Secret key for refresh tokens")
    PASSWORD_RESET_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32),
                                           description="Secret key for password reset tokens (separate from access tokens)")

    # CORS Settings
    BACKEND_CORS_ORIGINS: str | list[str] = Field("", description="Allowed CORS origins")

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
        """
        Ensures CORS settings return a valid list.

        Returns:
            list[str]: List of allowed CORS origins.
        """
        return list(set(self.BACKEND_CORS_ORIGINS + [self.FRONTEND_HOST, self.BACKEND_HOST]))

    # Detect Docker Environment
    DOCKERIZED: bool = Field(default_factory=lambda: False, description="Detects if the app runs inside Docker")

    # Database Configuration
    DATABASE_TYPE: Literal["sqlite", "postgres", "mysql"] = "postgres"
    DB_HOST: str = Field(default="localhost", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_USER: str = "swx_user"
    DB_PASSWORD: str = "changeme"
    DB_NAME: str = "swx_db"

    @property
    def ASYNC_SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Generates a dynamic async database connection URL.

        Returns:
            str: The full async database connection string.
        """
        db_host = "db" if self.DOCKERIZED else self.DB_HOST

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
        db_host = "db" if self.DOCKERIZED else self.DB_HOST

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
        return all([self.SMTP_HOST, self.SMTP_USER, self.SMTP_PASSWORD, self.EMAILS_FROM_EMAIL])

    # Superuser Configuration
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "securepassword"

    # Redis Configuration (for rate limiting and caching)
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_PASSWORD: str | None = Field(default=None, description="Redis password")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_ENABLED: bool = Field(default=True, description="Enable Redis (disable for development without Redis)")

    @property
    def REDIS_URL(self) -> str:
        """
        Generates Redis connection URL.
        
        Returns:
            str: Redis connection URL
        """
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Instantiate settings
settings = Settings()
