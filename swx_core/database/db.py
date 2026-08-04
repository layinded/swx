"""
Database Connection Module
--------------------------
This module establishes the database connection, manages sessions,
and provides dependency injection for FastAPI routes.

Key Components:
- `engine`: SQLAlchemy engine for database connection.
- `SessionLocal`: Session factory for handling transactions.
- `get_db()`: FastAPI dependency for database sessions.
- `log_sql_execute()`: Logs executed SQL queries.
"""

from collections.abc import AsyncGenerator, Generator
from typing import Annotated

import fastapi
from fastapi import Depends
import sqlalchemy
from sqlalchemy import event, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
import sqlmodel
from sqlmodel import Session, create_engine

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger

# Build connect_args for statement timeout (PostgreSQL only)
_db_connect_args: dict[str, object] = {}
if settings.DB_STATEMENT_TIMEOUT_MS > 0 and settings.DATABASE_TYPE in ("postgres", "postgresql"):
    _db_connect_args["server_settings"] = {
        "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
    }

# Create the async database engine with configurable connection pooling
async_engine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_use_lifo=settings.DB_POOL_USE_LIFO,
    connect_args=_db_connect_args,
)

# Async session factory for creating new database sessions
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Create the sync database engine (for background tasks/migrations)
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,
    pool_size=settings.DB_SYNC_POOL_SIZE,
    max_overflow=settings.DB_SYNC_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args=_db_connect_args,
)

# Sync session factory (legacy/isolated usage only)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection for async database session management in FastAPI.

    Yields:
        AsyncSession: A new database session that is automatically closed after use.
    """
    async with AsyncSessionLocal() as session:
        yield session

def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database session management in FastAPI.

    Yields:
        Session: A new database session that is automatically closed after use.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Log all executed SQL queries for debugging purposes
@event.listens_for(Engine, "before_cursor_execute")
def log_sql_execute(conn, cursor, statement, parameters, context, executemany):
    """
    SQLAlchemy event listener to log SQL queries before execution.

    Args:
        conn: Database connection.
        cursor: Database cursor.
        statement (str): The SQL statement being executed.
        parameters (tuple): Query parameters.
        context: Execution context.
        executemany: Boolean indicating batch execution.
    """
    logger.debug(f"SQL QUERY: {statement} | Params: {parameters}")

# FastAPI Dependency Injection for session usage in routes
SessionDep = Annotated[AsyncSession, Depends(get_async_db)]
SyncSessionDep = Annotated[Session, Depends(get_db)]

# Convenience aliases for backward compatibility
# These match the pattern used throughout the framework
get_session = get_async_db  # Alias for common usage pattern

# Backward-compat alias: older swx-core consumers (and some internal modules)
# imported ``async_session`` as a context-manager session factory.
# The canonical name is ``AsyncSessionLocal``, but we re-export under
# the old name so existing code keeps working.
async_session = AsyncSessionLocal