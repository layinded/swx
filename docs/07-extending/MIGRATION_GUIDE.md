# Migration Guide: SwX v1.x to v2.0

**Version:** 2.0.0  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Overview](#overview)
2. [Breaking Changes](#breaking-changes)
3. [New Features in v2.0](#new-features-in-v20)
4. [Migration Steps](#migration-steps)
5. [Code Migration Examples](#code-migration-examples)
6. [CLI Migration](#cli-migration)
7. [Configuration Changes](#configuration-changes)
8. [Troubleshooting](#troubleshooting)

---

## Overview

SwX v2.0 introduces significant improvements while maintaining backward compatibility where possible. This guide will help you migrate from v1.x to v2.0.

### Upgrade Timeline

| Project Size | Estimated Time | Difficulty |
|-------------|-----------------|------------|
| Small project (< 10 models) | 1-2 hours | Easy |
| Medium project (10-30 models) | 2-4 hours | Medium |
| Large project (30+ models) | 4-8 hours | Medium |

---

## Breaking Changes

### 1. BaseController/BaseService/BaseRepository Pattern

**v1.x (Legacy):**
```python
# Manual CRUD functions
class ProductRepository:
    @staticmethod
    def get_all(session: Session) -> list[Product]:
        return session.exec(select(Product)).all()
    
    @staticmethod
    def get_by_id(session: Session, id: UUID) -> Product | None:
        return session.get(Product, id)

class ProductService:
    @staticmethod
    def get_all(session: Session) -> list[Product]:
        return ProductRepository.get_all(session)
```

**v2.0 (New):**
```python
# Base classes with automatic CRUD
class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())
```

**Migration:** Use `swx make:resource Product --base` to generate new code, or manually update existing code.

### 2. SessionDep Changes

**v1.x:**
```python
from swx_core.database.db import SessionDep

@router.get("/products")
async def list_products(session: SessionDep):
    return ProductRepository.get_all(session)
```

**v2.0:**
```python
from swx_core.database.db import SessionDep

# Same pattern, but with base classes:
@router.get("/products")
async def list_products(session: SessionDep):
    repo = ProductRepository()
    return await repo.find_all()
```

**Note:** SessionDep is still supported. Base classes work with both sync and async sessions.

### 3. Utility Imports

**v1.x:**
```python
# Imports may have been scattered
from swx_core.pagination import PaginatedResponse
from swx_core.response import APIResponse
```

**v2.0:**
```python
# Centralized imports
from swx_core.utils import (
    PaginatedResponse,
    APIResponse,
    success,
    error,
)
```

---

## New Features in v2.0

### 1. Controller-Service-Repository Pattern

```python
# Auto-generated CRUD endpoints
class ProductController(BaseController[Product, Create, Update, Public]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
        )
        self.register_routes()
    
    # Custom routes
    def register_routes(self):
        @self.router.get("/search")
        async def search(q: str):
            return await self.search(q, ["name", "description"])

# Endpoints automatically created:
# GET    /products          - List with pagination
# GET    /products/{id}     - Get by ID
# POST   /products          - Create
# PUT    /products/{id}     - Update
# DELETE /products/{id}     - Delete
```

### 2. Unit of Work Pattern

```python
from swx_core.utils.unit_of_work import UnitOfWork

async with UnitOfWork() as uow:
    user = await uow.repository(UserRepository).create(user_data)
    order = await uow.repository(OrderRepository).create(order_data)
    await uow.commit()  # Single transaction
```

### 3. Query Filters

```python
from swx_core.utils.filters import FilterBuilder, SortBuilder

filters = FilterBuilder()
    .eq(Product.is_active, True)
    .gte(Product.price, min_price)
    .lte(Product.price, max_price)
    .contains(Product.name, search_query)

query = filters.apply(select(Product))
results = await session.execute(query)
```

### 4. Improved Pagination

```python
from swx_core.utils.pagination import PaginatedResponse

@router.get("/products")
async def list_products(page: int = 1, per_page: int = 20):
    repo = ProductRepository()
    result = await repo.paginate(page=page, per_page=per_page)
    return PaginatedResponse.create(
        data=result['data'],
        total=result['total'],
        page=page,
        per_page=per_page
    )
```

### 5. Database Connection Pooling

```python
# v2.0 includes connection pooling with health checks:
async_engine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # Detect stale connections
    pool_recycle=3600,   # Recycle after 1 hour
)
```

---

## Migration Steps

### Step 1: Update Dependencies

```bash
# Update pyproject.toml or requirements.txt
pip install swx-core>=2.0.0

# Or with specific version
pip install swx-core==2.0.0
```

### Step 2: Update Models

Most models remain unchanged. If you used mixins:

```python
# v1.x
from swx_core.models.base import Base

class Product(Base, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# v2.0 - Use model mixins
from swx_core.utils.mixins import FullModelMixin

class Product(FullModelMixin, table=True):
    # Automatically includes: id, created_at, updated_at, is_deleted
    name: str
    price: float
```

### Step 3: Migrate Repositories

```bash
# Generate using base classes
swx make:repository Product --base

# Or manually update:
```

```python
# v1.x
class ProductRepository:
    @staticmethod
    def get_all(session: Session) -> list[Product]:
        return session.exec(select(Product)).all()

# v2.0
class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)
    
    # Methods now available:
    # - find_by_id, find_all, find_by
    # - create, update, delete
    # - soft_delete, restore
    # - count, exists
    # - search, paginate
```

### Step 4: Migrate Services

```python
# v1.x
class ProductService:
    @staticmethod
    def create(session: Session, data: dict) -> Product:
        product = Product(**data)
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

# v2.0
class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())
    
    # Methods now available:
    # - get, get_or_fail, list
    # - create (with events), update (with events), delete (with events)
    # - validate_create, validate_update
    # - before_create, after_create, before_update, after_update
```

### Step 5: Migrate Controllers

```python
# v1.x - Manual endpoints
@router.get("/products")
async def list_products(session: SessionDep):
    return ProductService.list(session)

# v2.0 - BaseController pattern
class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
        )
        self.register_routes()
```

---

## Code Migration Examples

### Example 1: User Management

**v1.x:**
```python
# user_repository.py
class UserRepository:
    @staticmethod
    def get_by_email(session: Session, email: str) -> User | None:
        return session.exec(select(User).where(User.email == email)).first()

# user_service.py
class UserService:
    @staticmethod
    def create_user(session: Session, data: dict) -> User:
        user = User(**data)
        user.password = hash_password(data['password'])
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

# user_controller.py
class UserController:
    @staticmethod
    def get_user(session: Session, user_id: UUID) -> User:
        user = UserRepository.get_by_id(session, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        return user
```

**v2.0:**
```python
# user_repository.py
class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(model=User)
    
    async def find_by_email(self, email: str) -> User | None:
        return await self.find_one_by(email=email)

# user_service.py
class UserService(BaseService[User, UserRepository]):
    def __init__(self):
        super().__init__(repository=UserRepository())
    
    async def validate_create(self, data: dict) -> None:
        # Validate email uniqueness
        if await self.repository.exists_by(email=data.get('email')):
            raise ValueError("Email already registered")
    
    async def before_create(self, data: dict) -> dict:
        # Hash password before saving
        data['password'] = hash_password(data['password'])
        return data

# user_controller.py
class UserController(BaseController[User, UserCreate, UserUpdate, UserPublic]):
    def __init__(self):
        super().__init__(
            model=User,
            schema_public=UserPublic,
            schema_create=UserCreate,
            schema_update=UserUpdate,
            prefix="/users",
        )
        self.register_routes()
```

### Example 2: Filtering and Pagination

**v1.x:**
```python
@router.get("/products")
async def list_products(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    name: str | None = None,
    category: str | None = None,
):
    query = select(Product)
    if name:
        query = query.where(Product.name.ilike(f"%{name}%"))
    if category:
        query = query.where(Product.category == category)
    query = query.offset(skip).limit(limit)
    return session.exec(query).all()
```

**v2.0:**
```python
from swx_core.utils.filters import FilterBuilder

@router.get("/products")
async def list_products(
    skip: int = 0,
    limit: int = 100,
    name: str | None = None,
    category: str | None = None,
):
    repo = ProductRepository()
    
    filters = FilterBuilder()
    if name:
        filters.contains(Product.name, name)
    if category:
        filters.eq(Product.category, category)
    
    return await repo.find_by(skip=skip, limit=limit, **filters.build_filters())
```

---

## CLI Migration

### Generation Commands

**v1.x:**
```bash
swx make:resource Product
# Generated static functions
```

**v2.0:**
```bash
# Use --base flag for new patterns
swx make:resource Product --base

# Or use legacy patterns
swx make:resource Product
```

### Generated Files

**v1.x (Legacy):**
```python
# Generated static functions with manual CRUD
class ProductRepository:
    @staticmethod
    def get_all(session: Session) -> list[Product]:
        return session.exec(select(Product)).all()
```

**v2.0 (Base Classes):**
```python
# Generated with BaseController, BaseService, BaseRepository
class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)
    # Automatic: find_by_id, find_all, create, update, delete, etc.
```

---

## Configuration Changes

### Discovery Configuration

**v1.x:**
```python
# Hardcoded swx_app path
# No configuration needed
```

**v2.0:**
```python
# Configurable app name
import os
os.environ["SWX_APP_NAME"] = "my_app"

# Or in code
from swx_core.config.discovery import DiscoveryConfig
discovery = DiscoveryConfig(app_name="my_app", app_base="/path/to/my_app")
```

### Database Configuration

**v1.x:**
```python
# Basic connection
async_engine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
    pool_size=20,
)
```

**v2.0:**
```python
# Enhanced with connection pooling
async_engine = create_async_engine(
    str(settings.ASYNC_SQLALCHEMY_DATABASE_URI),
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,   # NEW: Health checks
    pool_recycle=3600,    # NEW: Recycle connections
)
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Issue:**
```python
ImportError: cannot import name 'PaginatedResponse' from 'swx_core.pagination'
```

**Solution:**
```python
# Old import
from swx_core.pagination import PaginatedResponse

# New import
from swx_core.utils import PaginatedResponse
```

#### 2. Session Type Errors

**Issue:**
```python
TypeError: 'AsyncSession' object is not iterable
```

**Solution:**
```python
# BaseRepository and BaseService use async sessions
# Make sure you're using async/await:

# Wrong
products = ProductRepository().find_all()

# Correct
products = await ProductRepository().find_all()
```

#### 3. Missing Repository Methods

**Issue:**
```python
AttributeError: 'ProductRepository' object has no attribute 'find_by_sku'
```

**Solution:**
```python
# Add custom methods to your repository
class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)
    
    # Add your custom methods
    async def find_by_sku(self, sku: str) -> Product | None:
        return await self.find_one_by(sku=sku)
```

#### 4. Event Bus Not Working

**Issue:**
```python
AttributeError: module 'swx_core.events' has no attribute 'EventBus'
```

**Solution:**
```python
# Make sure events are initialized
from swx_core.events import EventBus

# Register handlers before app starts
@EventBus.on("product.created")
async def handle_product_created(event):
    pass
```

### Deprecation Warnings

```python
# v1.x (deprecated)
from swx_core.middleware import CORS_MIDDLEWARE  # Not available

# v2.0 (correct)
from swx_core.middleware import setup_cors_middleware

def apply_middleware(app):
    setup_cors_middleware(app)
```

---

## Testing Your Migration

### Verify Installation

```python
# test_migration.py
from swx_core.utils import (
    BaseController,
    BaseService,
    BaseRepository,
    PaginatedResponse,
    FilterBuilder,
    UnitOfWork,
)

print("✅ All imports working correctly!")
```

### Run Tests

```bash
# Run your test suite
pytest tests/

# Check for deprecated imports
grep -r "from swx_core.pagination import" my_app/
grep -r "from swx_core.response import" my_app/
```

### Database Migration

```bash
# Generate migration for new models
alembic revision --autogenerate -m "Update models for v2.0"

# Apply migration
alembic upgrade head
```

---

## Getting Help

- **Documentation:** [docs/04-core-concepts/BASE_CLASSES.md](docs/04-core-concepts/BASE_CLASSES.md)
- **Examples:** [docs/04-core-concepts/USAGE_EXAMPLES.md](docs/04-core-concepts/USAGE_EXAMPLES.md)
- **GitHub Issues:** Report migration issues
- **Migration Support:** Create an issue with `[migration]` tag

---

**Status:** Migration guide complete. Ready for v2.0 upgrade.