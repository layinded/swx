"""
Database Module
---------------
Database connection, session management, and utilities.

Key Components:
- AsyncSessionLocal: Async session factory for FastAPI routes
- SessionLocal: Sync session factory for background tasks
- async_engine: Lazy proxy for async SQLAlchemy engine
- engine: Lazy proxy for sync SQLAlchemy engine
- get_async_engine(): Explicit lazy-init for async engine
- get_engine(): Explicit lazy-init for sync engine
- reset_engine(): Dispose engines and clear cached refs (test teardown)
- get_async_db: FastAPI dependency for async sessions
- get_db: FastAPI dependency for sync sessions
- SessionDep: Type annotation for async session dependency
- SyncSessionDep: Type annotation for sync session dependency
"""

from swx_core.database.db import (
    # Lazy engine access
    async_engine,
    engine,
    get_async_engine,
    get_engine,
    reset_engine,
    # Session factories
    AsyncSessionLocal,
    SessionLocal,
    async_session,
    # Dependency generators
    get_async_db,
    get_db,
    # Type annotations
    SessionDep,
    SyncSessionDep,
    # Aliases
    get_session,
)

__all__ = [
    # Lazy engine access
    "async_engine",
    "engine",
    "get_async_engine",
    "get_engine",
    "reset_engine",
    # Session factories
    "AsyncSessionLocal",
    "SessionLocal",
    "async_session",
    # Dependency generators
    "get_async_db",
    "get_db",
    # Type annotations
    "SessionDep",
    "SyncSessionDep",
    # Aliases
    "get_session",
]