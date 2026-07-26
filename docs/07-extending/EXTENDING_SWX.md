# Extending SwX-API

**Version:** 2.9.0
**Last Updated:** 2026-07-23

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Overview](#architecture-overview)
3. [Directory Structure](#directory-structure)
4. [Extension Patterns](#extension-patterns)
5. [Adding New Features](#adding-new-features)
6. [Best Practices](#best-practices)
7. [Common Patterns](#common-patterns)

---

## Overview

SwX-API is designed to be **extensible** while keeping framework code (`swx_core/`) and application code (`swx_app/`) separate. This guide shows how to extend the framework safely.

### Key Principles

1. **Framework vs Application** - framework code in `swx_core/`, app code in `swx_app/`
2. **Automatic Discovery** - routes and models are discovered automatically
3. **Layered Architecture** - Routes → Controllers → Services → Repositories → Models
4. **Domain Separation** - Admin, User, and System domains
5. **Permission-Based** - all endpoints are protected by permissions

---

## Architecture Overview

### Framework Structure

**`swx_core/` - Framework Code:**
- Core models (User, AdminUser, Team, Role, Permission, etc.)
- Authentication and authorization
- RBAC and policy engine
- Billing and entitlements
- Rate limiting and audit logging
- Background jobs and alerting
- Database and middleware

**`swx_app/` - Application Code:**
- Application-specific models
- Application routes
- Application services
- Application repositories
- Application controllers

### Separation of Concerns

**Framework (`swx_core/`):**
- Reusable across applications
- Framework-level functionality
- Core infrastructure
- Do not modify

**Application (`swx_app/`):**
- Application-specific logic
- Business domain models
- Custom features
- Safe to modify

---

## Directory Structure

### Framework Structure

```
swx_core/
├── auth/              # Authentication (admin, user, system)
├── models/            # Core models (User, Team, Role, etc.)
├── routes/            # Core routes (admin, user, utils)
├── services/          # Core services (auth, billing, etc.)
├── repositories/      # Core repositories
├── controllers/       # Core controllers
├── rbac/              # RBAC helpers
├── security/          # Security utilities
├── database/          # Database setup
├── middleware/        # Middleware (CORS, logging, rate limit)
└── config/            # Configuration
```

### Application Structure

```
swx_app/
├── models/            # Application models
├── routes/            # Application routes
├── services/          # Application services
├── repositories/      # Application repositories
├── controllers/       # Application controllers
└── tests/             # Application tests
```

### Automatic Discovery

**Routes:**
- Routes in `swx_core/routes/` automatically loaded
- Routes in `swx_app/routes/` automatically loaded
- Routes discovered at startup

**Models:**
- Models in `swx_core/models/` automatically registered
- Models in `swx_app/models/` automatically registered
- Models discovered at startup

---

## Route Module Structure

Each route directory needs an `__init__.py` that exports a **module-level `router` variable** for discovery and mounting.

### Route Directory Pattern

```
swx_app/routes/
├── __init__.py           # Exports module-level router
├── v1/
│   ├── __init__.py       # Aggregates all v1 routers
│   ├── product_route.py
│   └── order_route.py
└── v2/
    ├── __init__.py       # Aggregates all v2 routers
    └── product_route.py
```

### `__init__.py` Pattern (CRITICAL)

Each `__init__.py` must create a module-level `router` that aggregates sub-routers:

```python
# swx_app/routes/v1/__init__.py
from fastapi import APIRouter
from .product_route import router as product_router
from .order_route import router as order_router

# CRITICAL: Module-level router variable
router = APIRouter()
router.include_router(product_router)
router.include_router(order_router)

__all__ = ["router"]
```

### Why This Matters

Without the module-level `router` variable:
- Routes may appear "registered" in logs but still **return 404**
- SwX route discovery expects `__init__.py` to export `router`
- Individual route files define their own `router`, but `__init__.py` must aggregate them

### Example: Auth Routes Directory

```python
# swx_app/routes/auth/__init__.py
from fastapi import APIRouter
from .login_route import router as login_router
from .register_route import router as register_router
from .password_route import router as password_router

router = APIRouter()
router.include_router(login_router)
router.include_router(register_router)
router.include_router(password_router)
```

### Individual Route File Pattern

```python
# swx_app/routes/auth/login_route.py
from fastapi import APIRouter

router = APIRouter(prefix="/login", tags=["auth"])

@router.post("/")
async def login(...):
    ...

# No __all__ needed - imported via __init__.py
```

---

## Extension Patterns

### Pattern 1: Profile Extension (Extending Framework Tables)

Create a separate table linked 1:1 to a framework table (e.g., `swx_users`):

```python
class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="swx_users.id", unique=True, index=True)
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-1-one-to-one-profile-extension) for the complete step-by-step guide.**

### Pattern 2: Composition with Mixins

Use framework mixins for common fields on new models:

```python
from swx_core.utils.mixins import FullModelMixin

class Product(FullModelMixin, table=True):
    __tablename__ = "product"
    name: str = Field(max_length=255)
    price: float = Field(ge=0)
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-2-composition-with-mixins) for all available mixins.**

### Pattern 3: Feature Registry Extension

Register new billable features without modifying framework code:

```python
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureDefinition
from swx_core.models.billing import FeatureType

FeatureRegistry.register(FeatureDefinition(
    key="custom.branding",
    name="Custom Branding",
    description="Customize application branding.",
    feature_type=FeatureType.BOOLEAN,
))
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-3-feature-registry-extension) for the complete feature registration guide.**

### Pattern 4: CLI Resource Scaffolding

Generate a complete CRUD resource:

```bash
swx make:resource Product          # Legacy pattern
swx make:resource Product --base   # Base class pattern (recommended)
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-4-cli-resource-scaffolding) for scaffolding options.**

### Pattern 5: Base Class Pattern

Use `BaseRepository`, `BaseService`, and `BaseController` for CRUD with minimal code:

```python
from swx_core.repositories.base import BaseRepository
from swx_core.services.base import BaseService
from swx_core.controllers.base import BaseController

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())

class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(model=Product, schema_public=ProductPublic,
                         schema_create=ProductCreate, schema_update=ProductUpdate,
                         prefix="/products")
        self.register_routes()
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-5-base-class-pattern-crud) for the complete base class guide.**

### Pattern 6: Service Layer Extension

Extend core services or compose custom logic:

```python
from swx_core.services.user_service import UserService as CoreUserService

class ExtendedUserService(CoreUserService):
    async def get_user_with_profile(self, db, user_id: UUID) -> dict:
        user = await self.get(db, user_id)
        profile = await self.get_profile(db, user_id)
        return {**user.model_dump(), "profile": profile}
```

> **See [Extending Models](./EXTENDING_MODELS.md#pattern-6-service-layer-extension) for composition and event hooks.**

---

## Detailed Guides

For detailed documentation on each extension pattern, see:

- **[Extending Models](./EXTENDING_MODELS.md)** — Complete guide with step-by-step examples for all six patterns
- **[Custom Models](./CUSTOM_MODELS.md)** — Model patterns, relationships, and migration guide
- **[Adding Features](./ADDING_FEATURES.md)** — Feature development workflow
- **[Adding Entitlements](./ADDING_ENTITLEMENTS.md)** — Billing and entitlement integration

---

### Pattern 7: Adding New Models (Legacy)

**Step 1: Create Model**
```python
# swx_app/models/product.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from uuid import UUID, uuid4
from datetime import datetime

class ProductBase(SQLModel):
    name: str = Field(max_length=255)
    description: str | None = None
    price: float
    is_active: bool = Field(default=True)

class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    is_active: bool | None = None

class ProductPublic(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True
```

**Step 2: Create Migration**
```bash
# Generate migration
alembic revision --autogenerate -m "Add product table"

# Review and apply
alembic upgrade head
```

**Step 3: Export Model**
```python
# swx_app/models/__init__.py
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic

__all__ = ["Product", "ProductCreate", "ProductUpdate", "ProductPublic"]
```

### Pattern 8: Adding New Routes (Legacy)

**Option 1: Use CLI Generator (Recommended)**

The `swx make:resource` command generates complete CRUD routes with authentication included:

```bash
swx make:resource product
```

**This generates:**
- ✅ Model (with Base, Create, Update, Public schemas)
- ✅ Repository (CRUD operations)
- ✅ Service (business logic layer)
- ✅ Controller (request handling)
- ✅ Routes (with `UserDep` authentication included by default)

**After generation, add RBAC or policies:**
```python
# swx_app/routes/product_route.py
from swx_core.rbac.dependencies import require_permission

@router.get("/", response_model=list[ProductPublic])
async def list_products(
    session: SessionDep,
    current_user: UserDep,  # ✅ Already included by CLI
    _permission: None = Depends(require_permission("product:read")),  # Add RBAC
):
    ...
```

**Option 2: Manual Route Creation**

**Step 1: Create Repository**
```python
# swx_app/repositories/product_repository.py
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.product import Product, ProductCreate, ProductUpdate

async def get_product_by_id(session: AsyncSession, product_id: UUID) -> Product | None:
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_all_products(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Product]:
    stmt = select(Product).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def create_product(session: AsyncSession, product_in: ProductCreate) -> Product:
    product = Product(**product_in.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

async def update_product(session: AsyncSession, product: Product, product_in: ProductUpdate) -> Product:
    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

async def delete_product(session: AsyncSession, product: Product) -> None:
    await session.delete(product)
    await session.commit()
```

**Step 2: Create Service**
```python
# swx_app/services/product_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.product import Product, ProductCreate, ProductUpdate
from swx_app.repositories.product_repository import (
    get_product_by_id,
    get_all_products,
    create_product,
    update_product,
    delete_product,
)
from fastapi import HTTPException

async def get_product_service(session: AsyncSession, product_id: UUID) -> Product:
    product = await get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

async def list_products_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Product]:
    return await get_all_products(session, skip, limit)

async def create_product_service(session: AsyncSession, product_in: ProductCreate) -> Product:
    return await create_product(session, product_in)

async def update_product_service(
    session: AsyncSession, product_id: UUID, product_in: ProductUpdate
) -> Product:
    product = await get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return await update_product(session, product, product_in)

async def delete_product_service(session: AsyncSession, product_id: UUID) -> None:
    product = await get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await delete_product(session, product)
```

**Step 3: Create Controller**
```python
# swx_app/controllers/product_controller.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.product import Product, ProductCreate, ProductUpdate
from swx_app.services.product_service import (
    get_product_service,
    list_products_service,
    create_product_service,
    update_product_service,
    delete_product_service,
)

async def get_product_controller(session: AsyncSession, product_id: UUID) -> Product:
    return await get_product_service(session, product_id)

async def list_products_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Product]:
    return await list_products_service(session, skip, limit)

async def create_product_controller(session: AsyncSession, product_in: ProductCreate) -> Product:
    return await create_product_service(session, product_in)

async def update_product_controller(
    session: AsyncSession, product_id: UUID, product_in: ProductUpdate
) -> Product:
    return await update_product_service(session, product_id, product_in)

async def delete_product_controller(session: AsyncSession, product_id: UUID) -> None:
    await delete_product_service(session, product_id)
```

**Step 4: Create Routes**
```python
# swx_app/routes/product_route.py
from fastapi import APIRouter, Depends, Query
from uuid import UUID
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic
from swx_app.controllers import product_controller

router = APIRouter(prefix="/product", tags=["product"])

@router.get("/", response_model=list[ProductPublic])
async def list_products(
    session: SessionDep,
    current_user: UserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all products."""
    return await product_controller.list_products_controller(session, skip, limit)

@router.get("/{product_id}", response_model=ProductPublic)
async def get_product(
    product_id: UUID,
    session: SessionDep,
    current_user: UserDep,
):
    """Get product by ID."""
    return await product_controller.get_product_controller(session, product_id)

@router.post("/", response_model=ProductPublic, status_code=201)
async def create_product(
    product_in: ProductCreate,
    session: SessionDep,
    current_user: UserDep,
):
    """Create new product."""
    return await product_controller.create_product_controller(session, product_in)

@router.patch("/{product_id}", response_model=ProductPublic)
async def update_product(
    product_id: UUID,
    product_in: ProductUpdate,
    session: SessionDep,
    current_user: UserDep,
):
    """Update product."""
    return await product_controller.update_product_controller(session, product_id, product_in)

@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    session: SessionDep,
    current_user: UserDep,
):
    """Delete product."""
    await product_controller.delete_product_controller(session, product_id)
```

**Step 5: Export Route**
```python
# swx_app/routes/__init__.py
from swx_app.routes.product_route import router as product_router

__all__ = ["product_router"]
```

**Routes are automatically discovered and registered!**

---

## Adding New Features

### Feature Checklist

1. **Create Model** - Define data structure
2. **Create Migration** - Database schema changes
3. **Create Repository** - Database access layer
4. **Create Service** - Business logic layer
5. **Create Controller** - Request handling layer
6. **Create Routes** - API endpoints
7. **Add Permissions** - Access control
8. **Add Tests** - Test coverage

### Example: Product Feature

**Complete Feature:**
- Model: `Product` (name, description, price)
- Repository: CRUD operations
- Service: Business logic
- Controller: Request handling
- Routes: REST API endpoints
- Permissions: `product:read`, `product:write`, `product:delete`

---

## Best Practices

### ✅ DO

1. **Follow layered architecture**
   ```python
   # ✅ Good - Layered architecture
   Route → Controller → Service → Repository → Model
   ```

2. **Use dependency injection**
   ```python
   # ✅ Good - Dependency injection
   async def get_product(session: SessionDep, user: UserDep):
       ...
   ```

3. **Protect routes with permissions**
   ```python
   # ✅ Good - Permission check
   @router.post("/", dependencies=[Depends(require_permission("product:write"))])
   ```

4. **Use type hints**
   ```python
   # ✅ Good - Type hints
   async def get_product(product_id: UUID) -> Product:
       ...
   ```

5. **Handle errors gracefully**
   ```python
   # ✅ Good - Error handling
   if not product:
       raise HTTPException(status_code=404, detail="Product not found")
   ```

### ❌ DON'T

1. **Don't modify framework code**
   ```python
   # ❌ Bad - Modifying framework
   # swx_core/models/user.py - DON'T MODIFY
   
   # ✅ Good - Extend in application
   # swx_app/models/custom_user.py - OK
   ```

2. **Don't bypass layers**
   ```python
   # ❌ Bad - Bypassing layers
   @router.get("/")
   async def get_products(session: SessionDep):
       stmt = select(Product)  # Direct database access
   
   # ✅ Good - Use layers
   @router.get("/")
   async def get_products(session: SessionDep):
       return await product_service.list_products(session)
   ```

3. **Don't skip permissions**
   ```python
   # ❌ Bad - No permission check
   @router.delete("/{id}")
   async def delete_product(id: UUID):
       ...
   
   # ✅ Good - Permission check
   @router.delete("/{id}", dependencies=[Depends(require_permission("product:delete"))])
   async def delete_product(id: UUID):
       ...
   ```

---

## Common Patterns

### CRUD Pattern

**Standard CRUD operations:**
- `GET /resource/` - List resources
- `GET /resource/{id}` - Get resource by ID
- `POST /resource/` - Create resource
- `PATCH /resource/{id}` - Update resource
- `DELETE /resource/{id}` - Delete resource

### Permission Pattern

**Standard permissions:**
- `{resource}:read` - Read access
- `{resource}:write` - Write access
- `{resource}:delete` - Delete access

### Team-Scoped Pattern

**Team-scoped resources:**
- Resources belong to teams
- Team membership required
- Team-scoped permissions

---

## Next Steps

- Read [Extending Models](./EXTENDING_MODELS.md) for the complete extension patterns guide
- Read [Adding Features](./ADDING_FEATURES.md) for detailed feature addition
- Read [Adding Entitlements](./ADDING_ENTITLEMENTS.md) for billing integration
- Read [Adding Policies](./ADDING_POLICIES.md) for policy creation
- Read [Custom Models](./CUSTOM_MODELS.md) for model patterns

---

**Status:** Extending guide documented, ready for implementation.
