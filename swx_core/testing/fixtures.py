"""
SWX Test Fixtures
-----------------
Pytest fixtures for SWX-based applications.

Features:
- ``db_session``: Transaction-rollback-per-test async fixture.
  Each test runs inside a transaction that is rolled back after,
  providing fast, perfect isolation without table truncation.
- ``reset_engine``: Teardown helper that disposes engines between
  test sessions, preventing "Future attached to a different loop"
  errors when pytest-asyncio creates new event loops.

Usage in conftest.py::

    pytest_plugins = ["swx_core.testing.fixtures"]

Or import and register manually::

    from swx_core.testing.fixtures import db_session, _reset_engine_fixture
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database.db import get_async_engine, reset_engine as _reset_engine


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transaction-rollback database session for each test.

    Each test runs inside a DB transaction. On teardown the transaction
    is rolled back, so no test data persists. This is the fastest way
    to achieve test isolation with a real database.
    """
    eng = get_async_engine()
    async with eng.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await txn.rollback()


@pytest.fixture(scope="session", autouse=True)
def _reset_engine_fixture():
    """Dispose DB engines after the test session ends."""
    yield
    _reset_engine()