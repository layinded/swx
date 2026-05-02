"""
Database Service Provider.

Registers database services including:
- Database engine
- Session factory
- Session (scoped)
"""

from swx_core.providers.base import ServiceProvider


class DatabaseServiceProvider(ServiceProvider):
    """Register database services."""
    
    priority = 10  # Register early - other providers depend on this
    
    def register(self) -> None:
        """Register database bindings."""
        # Database engine (singleton)
        self.singleton("db.engine", self._create_engine)
        
        # Session factory (singleton)
        self.singleton("db.session_factory", self._create_session_factory)
        
        # Session (scoped - one per request)
        self.scoped("db.session", self._create_session)
        
        # Aliases for convenience
        self.alias("db.session", "session")
        self.alias("db.session", "AsyncSession")
    
    def boot(self) -> None:
        """Boot database services."""
        pass
    
    def _create_engine(self, app):
        """Create the database engine."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from swx_core.config.settings import settings
        
        return create_async_engine(
            str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
            echo=False,
            pool_size=20,
            max_overflow=10,
        )
    
    def _create_session_factory(self, app):
        """Create the session factory."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        
        engine = app.make("db.engine")
        return async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    def _create_session(self, app):
        """Create a session (scoped per request)."""
        factory = app.make("db.session_factory")
        return factory()