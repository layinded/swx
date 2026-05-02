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

# Create the async database engine with connection pooling
# Includes resilience features:
# - pool_pre_ping: Checks connection health before use (detects stale connections)
# - pool_recycle: Recycles connections after 1 hour (prevents MySQL "gone away" errors)
async_engine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
    echo=False,  # Disables verbose SQL logging for performance
    pool_size=20,  # Maintain up to 20 active connections
    max_overflow=10,  # Allow up to 10 extra connections when needed
    pool_pre_ping=True,  # Enable connection health checks (detect stale connections)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevent stale connections)
)

# Async session factory for creating new database sessions
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Create the sync database engine (for background tasks/migrations if needed)
# Same resilience features as async engine
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600,  # Recycle connections after 1 hour
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