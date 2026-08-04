"""
Database Module
---------------
Database connection, session management, and utilities.

Key Components:
- AsyncSessionLocal: Async session factory for FastAPI routes
- SessionLocal: Sync session factory for background tasks
- async_engine: Async SQLAlchemy engine
- engine: Sync SQLAlchemy engine
- get_async_db: FastAPI dependency for async sessions
- get_db: FastAPI dependency for sync sessions
- SessionDep: Type annotation for async session dependency
- SyncSessionDep: Type annotation for sync session dependency
"""

from swx_core.database.db import (
    # Engines
    async_engine,
    engine,
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
    # Engines
    "async_engine",
    "engine",
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