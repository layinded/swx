# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Database Configuration Settings Mixin.

Defines database connection configuration: database type, host/port/credentials,
connection URLs, pooling, and Alembic configuration.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettingsMixin(BaseSettings):
    """Database configuration."""

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

    # Database SSL (SOC 2 CC7.1)
    DATABASE_SSL_MODE: str = Field(
        default="prefer", description="PostgreSQL sslmode: require, prefer, disable. Production should use 'require'."
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
            return self._inject_ssl_mode(self.ASYNC_DATABASE_URL)

        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("mysql://"):
                url = url.replace("mysql://", "mysql+asyncmy://", 1)
            return self._inject_ssl_mode(url)

        db_host = self.DB_HOST

        if self.DATABASE_TYPE == "sqlite":
            return f"sqlite+aiosqlite:///./{self.DB_NAME}.db"
        elif self.DATABASE_TYPE == "mysql":
            return f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        base = f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        return self._inject_ssl_mode(base)

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self._strip_async_drivers(self.DATABASE_URL)
            return self._inject_ssl_mode(url)

        db_host = self.DB_HOST

        if self.DATABASE_TYPE == "sqlite":
            return f"sqlite:///./{self.DB_NAME}.db"
        elif self.DATABASE_TYPE == "mysql":
            return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        base = f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{db_host}:{self.DB_PORT}/{self.DB_NAME}"
        return self._inject_ssl_mode(base)

    @staticmethod
    def _strip_async_drivers(url: str) -> str:
        """Remove async driver suffixes from a database URL.

        Strips ``+asyncpg``, ``+aiosqlite``, ``+asyncmy`` so the URL
        is safe for a synchronous SQLAlchemy engine.  This is the inverse
        of :pyattr:`ASYNC_SQLALCHEMY_DATABASE_URI` which *adds* those
        suffixes.
        """
        # postgresql+asyncpg:// → postgresql://
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        # mysql+asyncmy:// → mysql://
        url = url.replace("mysql+asyncmy://", "mysql://", 1)
        # sqlite+aiosqlite:// → sqlite://
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        # Also handle the legacy ``postgres://`` shorthand which may carry
        # an async driver that was appended by an operator or CI config.
        url = url.replace("postgres+asyncpg://", "postgresql://", 1)
        return url

    def _inject_ssl_mode(self, url: str) -> str:
        if self.DATABASE_TYPE not in ("postgres", "postgresql") or self.DATABASE_SSL_MODE == "prefer":
            return url
        if self.DATABASE_SSL_MODE == "disable":
            sep = "&" if "?" in url else "?"
            return url + sep + "sslmode=disable"
        if self.DATABASE_SSL_MODE == "require":
            if "sslmode=" in url:
                return url
            sep = "&" if "?" in url else "?"
            return url + sep + "sslmode=require"
        return url
