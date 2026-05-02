"""
Test Utilities
--------------
Testing utilities for FastAPI applications.
"""

import uuid
import asyncio
from typing import Dict, Any, Optional, Type, Callable, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from swx_core.database.db import get_session
from swx_core.models.base import Base


class TestSession:
    """
    Test session context manager for database operations.
    
    Usage:
        async with TestSession() as session:
            user = await session.execute(select(User))
            assert user is not None
    """
    
    def __init__(self, test_session: AsyncSession):
        self.session = test_session
    
    async def __aenter__(self):
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()


class TestDatabase:
    """
    Test database setup and teardown.
    
    Usage:
        test_db = TestDatabase()
        
        @pytest.fixture(scope="module")
        async def setup_db():
            await test_db.create()
            yield
            await test_db.drop()
        
        @pytest.fixture
        async def session():
            async with test_db.session() as s:
                yield s
    """
    
    def __init__(
        self,
        db_url: str = "sqlite+aiosqlite:///:memory:",
        connect_args: Dict[str, Any] = None,
    ):
        self.db_url = db_url
        self.connect_args = connect_args or {"check_same_thread": False}
        self.engine = None
        self.async_session_maker = None
    
    async def create(self):
        """Create tables and initialize."""
        from sqlalchemy.ext.asyncio import create_async_engine
        
        self.engine = create_async_engine(
            self.db_url,
            connect_args=self.connect_args,
            echo=False,
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop(self):
        """Drop all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def session(self) -> AsyncSession:
        """Get a new session."""
        async with self.async_session_maker() as session:
            async with session.begin():
                yield session
    
    @asynccontextmanager
    async def get_session(self):
        """Context manager for session."""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


class TestClientWithDB(TestClient):
    """
    Test client with database session injection.
    
    Usage:
        @pytest.fixture
        def client():
            with TestClientWithDB(app) as c:
                yield c
        
        def test_create_user(client):
            response = client.post("/users", json={"name": "Test"})
            assert response.status_code == 201
    """
    
    def __init__(self, app: FastAPI, test_db: TestDatabase, **kwargs):
        self.test_db = test_db
        super().__init__(app, **kwargs)
    
    async def async_request(self, method: str, url: str, **kwargs):
        """Make async request with session override."""
        async with self.test_db.get_session() as session:
            # Override dependency injection
            self.app.dependency_overrides[get_session] = lambda: session
            
            async with AsyncClient(app=self.app, base_url="http://test") as client:
                response = await client.request(method, url, **kwargs)
            
            # Clear override
            self.app.dependency_overrides.clear()
            
            return response


class ModelFactory:
    """
    Factory for creating test model instances.
    
    Usage:
        class UserFactory(ModelFactory):
            model = User
            
            @classmethod
            def defaults(cls):
                return {
                    "email": faker.email(),
                    "name": faker.name(),
                }
        
        user = UserFactory.create()
        admin_user = UserFactory.create(is_admin=True)
    """
    
    model: Type = None
    
    @classmethod
    def defaults(cls) -> Dict[str, Any]:
        """Default values for model."""
        return {}
    
    @classmethod
    def create(cls, **kwargs) -> Any:
        """Create a model instance."""
        if cls.model is None:
            raise ValueError("Model class must be specified")
        
        defaults = cls.defaults()
        defaults.update(kwargs)
        
        instance = cls.model(**defaults)
        return instance
    
    @classmethod
    def create_batch(cls, count: int, **kwargs) -> List[Any]:
        """Create multiple model instances."""
        return [cls.create(**kwargs) for _ in range(count)]
    
    @classmethod
    def build(cls, **kwargs) -> Dict[str, Any]:
        """Build a dictionary of values."""
        defaults = cls.defaults()
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def build_batch(cls, count: int, **kwargs) -> List[Dict[str, Any]]:
        """Build multiple dictionaries of values."""
        return [cls.build(**kwargs) for _ in range(count)]


class AsyncTestMixin:
    """
    Mixin for async test utilities.
    
    Usage:
        class TestUsers(AsyncTestMixin):
            async def test_list_users(self):
                response = await self.async_get("/users")
                assert response.status_code == 200
    """
    
    async def async_get(self, client: AsyncClient, url: str, **kwargs):
        """Make async GET request."""
        return await client.get(url, **kwargs)
    
    async def async_post(self, client: AsyncClient, url: str, data: Dict, **kwargs):
        """Make async POST request."""
        return await client.post(url, json=data, **kwargs)
    
    async def async_put(self, client: AsyncClient, url: str, data: Dict, **kwargs):
        """Make async PUT request."""
        return await client.put(url, json=data, **kwargs)
    
    async def async_delete(self, client: AsyncClient, url: str, **kwargs):
        """Make async DELETE request."""
        return await client.delete(url, **kwargs)


def random_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def random_email() -> str:
    """Generate a random email."""
    return f"test_{random_uuid()[:8]}@example.com"


def random_string(length: int = 10) -> str:
    """Generate a random string."""
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def assert_response_status(response, expected_status: int):
    """Assert response status code."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response: {response.text}"
    )


def assert_response_json(response, expected_keys: List[str]):
    """Assert response contains expected keys."""
    data = response.json()
    for key in expected_keys:
        assert key in data, f"Expected key '{key}' not found in response"


def assert_model_equal(model, data: Dict, exclude: List[str] = None):
    """Assert model matches data dictionary."""
    exclude = exclude or []
    for key, value in data.items():
        if key not in exclude and hasattr(model, key):
            assert getattr(model, key) == value, (
                f"Model.{key} = {getattr(model, key)} != {value}"
            )


@asynccontextmanager
async def async_test_context():
    """Context manager for async tests."""
    loop = asyncio.get_event_loop()
    yield loop


# Fixtures utility
async def create_fixture_data(models: List[Dict[str, Any]], session: AsyncSession):
    """
    Create fixture data in database.
    
    Usage:
        @pytest.fixture
        async def users(session):
            data = [
                {"email": "user1@example.com", "name": "User One"},
                {"email": "user2@example.com", "name": "User Two"},
            ]
            return await create_fixture_data(data, session)
    """
    instances = []
    for model_data in models:
        instance = model_data.get("model")(**model_data.get("data", {}))
        session.add(instance)
        instances.append(instance)
    
    await session.commit()
    
    for instance in instances:
        await session.refresh(instance)
    
    return instances