"""
Database Connection Module
--------------------------
This module establishes the database connection, manages sessions,
and provides dependency injection for FastAPI routes.

Key Components:
- `get_async_engine()`: Lazy-initialised async engine (test-friendly).
- `get_engine()`: Lazy-initialised sync engine (test-friendly).
- `async_engine`: Module-level async engine (lazy proxy).
- `engine`: Module-level sync engine (lazy proxy).
- `AsyncSessionLocal`: Async session factory for FastAPI routes.
- `SessionLocal`: Sync session factory for background tasks/migrations.
- `get_db()`: FastAPI dependency for database sessions.
- `reset_engine()`: Dispose and recreate engines (for test teardown).
- `log_sql_execute()`: Logs executed SQL queries.
"""

from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, SingletonThreadPool, StaticPool, AsyncAdaptedQueuePool
from sqlmodel import Session, create_engine

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger


_POOL_CLASS_MAP = {
    "QueuePool": QueuePool,
    "NullPool": NullPool,
    "SingletonThreadPool": SingletonThreadPool,
    "StaticPool": StaticPool,
}


def _resolve_pool_class():
    cls = _POOL_CLASS_MAP.get(settings.DB_POOL_CLASS)
    if cls is None:
        raise ValueError(
            f"Unknown DB_POOL_CLASS '{settings.DB_POOL_CLASS}'. "
            f"Choose from: {', '.join(_POOL_CLASS_MAP)}"
        )
    return cls


def _async_database_url() -> str:
    if settings.TESTING and settings.TEST_DATABASE_URL:
        url = settings.TEST_DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    return str(settings.ASYNC_SQLALCHEMY_DATABASE_URI)


def _sync_database_url() -> str:
    if settings.TESTING and settings.TEST_DATABASE_URL:
        url = settings.TEST_DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url
    return str(settings.SQLALCHEMY_DATABASE_URI)


def _build_connect_args() -> dict[str, object]:
    connect_args: dict[str, object] = {}
    if (
        settings.DB_STATEMENT_TIMEOUT_MS > 0
        and settings.DATABASE_TYPE in ("postgres", "postgresql")
    ):
        connect_args["server_settings"] = {
            "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
        }
    return connect_args


_async_engine = None
_sync_engine = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        pool_class = _resolve_pool_class()
        if pool_class is QueuePool:
            pool_class = AsyncAdaptedQueuePool
        pool_kwargs: dict[str, object] = {}
        if pool_class is not NullPool:
            pool_kwargs = {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_use_lifo": settings.DB_POOL_USE_LIFO,
            }
        _async_engine = create_async_engine(
            _async_database_url(),
            echo=False,
            poolclass=pool_class,
            connect_args=_build_connect_args(),
            **pool_kwargs,
        )
    return _async_engine


def get_engine():
    global _sync_engine
    if _sync_engine is None:
        pool_class = _resolve_pool_class()
        pool_kwargs: dict[str, object] = {}
        if pool_class is not NullPool:
            pool_kwargs = {
                "pool_size": settings.DB_SYNC_POOL_SIZE,
                "max_overflow": settings.DB_SYNC_MAX_OVERFLOW,
                "pool_recycle": settings.DB_POOL_RECYCLE,
            }
        _sync_engine = create_engine(
            _sync_database_url(),
            echo=False,
            poolclass=pool_class,
            connect_args=_build_connect_args(),
            **pool_kwargs,
        )
    return _sync_engine


def reset_engine():
    """Dispose existing engines and clear cached references.

    Call this in test teardown to release connections and allow
    a fresh engine to be created on the next request.
    """
    global _async_engine, _sync_engine
    if _async_engine is not None:
        _async_engine.sync_engine.dispose()
        _async_engine = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None


class _LazyAsyncEngine:
    """Proxy that delegates all attribute access to the real async engine.

    This allows existing code that imports ``async_engine`` from
    ``swx_core.database.db`` to continue working without changes,
    while the actual engine is created lazily on first access.
    """

    def __getattr__(self, name):
        return getattr(get_async_engine(), name)

    def __repr__(self):
        eng = get_async_engine()
        return repr(eng)


class _LazySyncEngine:
    """Proxy that delegates all attribute access to the real sync engine."""

    def __getattr__(self, name):
        return getattr(get_engine(), name)

    def __repr__(self):
        eng = get_engine()
        return repr(eng)


async_engine = _LazyAsyncEngine()  # type: ignore[assignment]
engine = _LazySyncEngine()  # type: ignore[assignment]


def _build_async_session_factory():
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _build_sync_session_factory():
    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        expire_on_commit=False,
    )


AsyncSessionLocal = _build_async_session_factory()
SessionLocal = _build_sync_session_factory()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@event.listens_for(Engine, "before_cursor_execute")
def log_sql_execute(conn, cursor, statement, parameters, context, executemany):
    logger.debug(f"SQL QUERY: {statement} | Params: {parameters}")


SessionDep = Annotated[AsyncSession, Depends(get_async_db)]
SyncSessionDep = Annotated[Session, Depends(get_db)]

get_session = get_async_db

async_session = AsyncSessionLocal