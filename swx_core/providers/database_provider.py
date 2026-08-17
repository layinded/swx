"""
Database Service Provider.

Registers database services including:
- Database engine
- Session factory
- Session (scoped)
"""

from swx_core.database.db import get_async_engine
from swx_core.providers.base import ServiceProvider


class DatabaseServiceProvider(ServiceProvider):
    """Register database services."""

    priority = 10

    def register(self) -> None:
        """Register database bindings."""
        self.singleton("db.engine", self._create_engine)

        self.singleton("db.session_factory", self._create_session_factory)

        self.scoped("db.session", self._create_session)

        self.alias("db.session", "session")
        self.alias("db.session", "AsyncSession")

    def boot(self) -> None:
        pass

    def _create_engine(self, app):
        """Return the lazily-initialised async engine."""
        return get_async_engine()

    def _create_session_factory(self, app):
        """Create the session factory."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        return async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _create_session(self, app):
        """Create a session (scoped per request)."""
        factory = app.make("db.session_factory")
        return factory()