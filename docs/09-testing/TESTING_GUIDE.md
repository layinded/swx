# Testing Guide

**Version:** 2.21.0  
**Last Updated:** 2026-08-17

---

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Test Types](#test-types)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Running Tests](#running-tests)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API uses **pytest** for testing with comprehensive test coverage. This guide covers how to write and run tests effectively.

### Test Framework

- **pytest** - Test framework
- **TestClient** - FastAPI test client
- **SQLite in-memory** - Test database
- **Fixtures** - Reusable test setup

---

## Test Structure

### Directory Structure

```
swx_core/tests/
├── controllers/      # Controller tests
├── services/         # Service tests
├── repositories/     # Repository tests
├── routes/           # Route tests
├── models/           # Model tests
└── misc/             # Miscellaneous tests

swx_app/tests/
└── ...               # Application-specific tests
```

### Test File Naming

**Convention:**
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

**Examples:**
- `test_auth_controller.py`
- `test_user_service.py`
- `test_user_route.py`

---

## Test Types

### Unit Tests

**Purpose:** Test individual functions/methods

**Example:**
```python
# swx_core/tests/services/test_auth_service.py
async def test_login_user_service_success(test_db, mock_request):
    """Test successful user login."""
    user_create = UserCreate(
        email="test@example.com",
        password="password123"
    )
    user = await register_user_service(test_db, user_create, mock_request)
    
    form_data = OAuth2PasswordRequestForm(
        username=user.email,
        password="password123"
    )
    token = await login_user_service(test_db, form_data, mock_request)
    
    assert token.access_token is not None
    assert token.token_type == "bearer"
```

### Integration Tests

**Purpose:** Test component interactions

**Example:**
```python
# swx_core/tests/routes/test_auth_routes.py
def test_login_success(client, test_db):
    """Test login endpoint."""
    # Register user
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    
    # Login
    response = client.post("/api/auth/", data={
        "username": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### End-to-End Tests

**Purpose:** Test complete workflows

**Example:**
```python
# Full user simulation
python scripts/full_user_simulation.py
```

---

## Writing Tests

### Test Function Structure

**Basic Test:**
```python
def test_function_name():
    """Test description."""
    # Arrange
    # Act
    # Assert
    assert result == expected
```

### Controller Tests

**Example:**
```python
# swx_core/tests/controllers/test_auth_controller.py
@pytest.mark.asyncio
async def test_login_controller_success(test_db, mock_request):
    """Test login controller."""
    # Arrange
    form_data = OAuth2PasswordRequestForm(
        username="test@example.com",
        password="password123"
    )
    
    # Act
    token = await login_controller(test_db, form_data, mock_request)
    
    # Assert
    assert token.access_token is not None
    assert token.token_type == "bearer"
```

### Service Tests

**Example:**
```python
# swx_core/tests/services/test_user_service.py
@pytest.mark.asyncio
async def test_get_user_by_id_service(test_db):
    """Test get user by ID service."""
    # Arrange
    user = await create_user(test_db, ...)
    
    # Act
    result = await get_user_by_id_service(test_db, user.id)
    
    # Assert
    assert result.id == user.id
    assert result.email == user.email
```

### Route Tests

**Example:**
```python
# swx_core/tests/routes/test_auth_routes.py
def test_login_endpoint(client, test_db):
    """Test login endpoint."""
    # Arrange
    # Register user first
    client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123"
    })
    
    # Act
    response = client.post("/api/auth/", data={
        "username": "test@example.com",
        "password": "password123"
    })
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
```

---

## Test-Friendly Database Configuration

### The Problem

SWX Core's database engine was created at **module import time** with a fixed connection pool. This caused:

1. Engine binds to the first event loop at import time
2. pytest-asyncio creates new event loops per test → "Future attached to a different loop"
3. No built-in support for a separate test database
4. No `NullPool` option for test environments
5. No transaction-rollback-per-test pattern support

### The Solution: Lazy Engine + NullPool + Rollback Fixtures

SWX Core v2.21.0 introduces three features that solve these problems:

#### 1. Lazy Engine Initialization

The engine is no longer created at import time. Instead, use `get_async_engine()`:

```python
from swx_core.database.db import get_async_engine, reset_engine

# Engine is created on first access, not at import
engine = get_async_engine()

# Dispose and clear for test teardown
await reset_engine()
```

The module-level `async_engine` and `engine` are now **lazy proxies** that delegate to the real engine on first access. All existing code (`from swx_core.database.db import async_engine`) continues to work unchanged.

#### 2. Configurable Pool Class

Set `DB_POOL_CLASS=NullPool` in your test environment to disable connection pooling:

```bash
# .env.test
DB_POOL_CLASS=NullPool
TESTING=true
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/myapp_test
```

With `NullPool`, each request gets a fresh connection — no event loop binding issues.

#### 3. Transaction-Rollback-Per-Test Fixture

SWX Core ships a pytest plugin with a `db_session` fixture that wraps each test in a transaction and rolls it back after:

```python
# conftest.py — register the fixtures
pytest_plugins = ["swx_core.testing.fixtures"]
```

Then use `db_session` in your tests:

```python
@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(email="test@example.com", hashed_password="...")
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == "test@example.com"))
    assert result.scalar_one_or_none() is not None
    # Transaction is rolled back automatically — no data persists
```

#### 4. Engine Reset Between Test Sessions

The `_reset_engine_fixture` (autouse, session-scoped) disposes engines after the test session ends, preventing "Future attached to a different loop" errors.

#### 5. Environment-Based Test Configuration

For the simplest setup, use environment variables:

```python
# conftest.py
import pytest

@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("DB_POOL_CLASS", "NullPool")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/myapp_test")
```

Or in `.env.test`:

```bash
TESTING=true
DB_POOL_CLASS=NullPool
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/myapp_test
```

### Settings Reference

| Setting | Default | Purpose |
|---|---|---|
| `TESTING` | `False` | Enable test mode (lazy engine init, TEST_DATABASE_URL) |
| `TEST_DATABASE_URL` | `None` | Override DATABASE_URL when TESTING=true |
| `DB_POOL_CLASS` | `"QueuePool"` | SQLAlchemy pool class (`NullPool` for tests) |

### Public API

| Symbol | Module | Purpose |
|---|---|---|
| `get_async_engine()` | `swx_core.database.db` | Lazy-init async engine |
| `get_engine()` | `swx_core.database.db` | Lazy-init sync engine |
| `reset_engine()` | `swx_core.database.db` | Dispose engines and clear cached refs |
| `async_engine` | `swx_core.database.db` | Lazy proxy (backward-compatible) |
| `engine` | `swx_core.database.db` | Lazy proxy (backward-compatible) |
| `db_session` | `swx_core.testing.fixtures` | Rollback-per-test async fixture |
| `_reset_engine_fixture` | `swx_core.testing.fixtures` | Session-scoped engine teardown |

---

## Test Fixtures

### Database Fixture

**Standard Fixture:**
```python
@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

### Request Fixture

**Mock Request:**
```python
@pytest.fixture
def mock_request():
    """Mock request object."""
    return MagicMock()
```

### Client Fixture

**Test Client:**
```python
@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
```

### User Fixture

**Test User:**
```python
@pytest.fixture
async def test_user(test_db):
    """Create test user."""
    user = User(
        email="test@example.com",
        hashed_password=await get_password_hash("password123"),
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    return user
```

---

## Running Tests

### Run All Tests

**Basic:**
```bash
pytest
```

**With Coverage:**
```bash
pytest --cov=swx_core --cov=swx_app
```

**Verbose:**
```bash
pytest -v
```

### Run Specific Tests

**By File:**
```bash
pytest swx_core/tests/services/test_auth_service.py
```

**By Function:**
```bash
pytest swx_core/tests/services/test_auth_service.py::test_login_user_service_success
```

**By Pattern:**
```bash
pytest -k "test_login"
```

### Run Test Categories

**Unit Tests:**
```bash
pytest -m unit
```

**Integration Tests:**
```bash
pytest -m integration
```

**Slow Tests:**
```bash
pytest -m "not slow"
```

---

## Best Practices

### ✅ DO

1. **Use descriptive test names**
   ```python
   # ✅ Good - Descriptive
   def test_login_user_service_success():
       ...
   
   # ❌ Bad - Vague
   def test_login():
       ...
   ```

2. **Follow AAA pattern**
   ```python
   # ✅ Good - Arrange, Act, Assert
   def test_function():
       # Arrange
       user = create_user(...)
       
       # Act
       result = get_user(user.id)
       
       # Assert
       assert result.email == user.email
   ```

3. **Use fixtures for setup**
   ```python
   # ✅ Good - Use fixtures
   def test_function(test_db, test_user):
       ...
   ```

4. **Test both success and failure**
   ```python
   # ✅ Good - Test both
   def test_login_success():
       ...
   
   def test_login_failure():
       ...
   ```

5. **Isolate tests**
   ```python
   # ✅ Good - Isolated tests
   @pytest.fixture(scope="function")
   def test_db():
       # Fresh database per test
       ...
   ```

### ❌ DON'T

1. **Don't share state between tests**
   ```python
   # ❌ Bad - Shared state
   user = None  # Global variable
   
   def test_1():
       global user
       user = create_user()
   
   def test_2():
       # Uses user from test_1 - BAD
       ...
   
   # ✅ Good - Isolated
   @pytest.fixture
   def test_user():
       return create_user()
   ```

2. **Don't test implementation details**
   ```python
   # ❌ Bad - Implementation details
   def test_internal_variable():
       assert service._internal_var == value
   
   # ✅ Good - Public interface
   def test_public_method():
       result = service.public_method()
       assert result == expected
   ```

3. **Don't skip assertions**
   ```python
   # ❌ Bad - No assertions
   def test_function():
       result = do_something()
       # No assertion
   
   # ✅ Good - Assertions
   def test_function():
       result = do_something()
       assert result is not None
   ```

---

## Next Steps

- Read [Acceptance Testing](./ACCEPTANCE_TESTING.md) for acceptance test procedures
- Read [Seeding & Simulation](./SEEDING_AND_SIMULATION.md) for simulation tools
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production operations

---

**Status:** Testing guide documented, ready for implementation.
