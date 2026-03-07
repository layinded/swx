# Adding Features

**Version:** 1.0.0  
**Last Updated:** 2026-01-26  
**Updated:** CLI resource generation includes authentication by default

---

## Table of Contents

1. [Overview](#overview)
2. [Feature Development Process](#feature-development-process)
3. [Complete Example](#complete-example)
4. [Adding Permissions](#adding-permissions)
5. [Adding Routes](#adding-routes)
6. [Testing Features](#testing-features)
7. [Best Practices](#best-practices)

---

## Overview

This guide provides a **step-by-step process** for adding new features to SwX-API. Follow this process to ensure features are properly integrated with the framework.

### Feature Components

A complete feature includes:
1. **Model** - Data structure
2. **Migration** - Database schema
3. **Repository** - Database access
4. **Service** - Business logic
5. **Controller** - Request handling
6. **Routes** - API endpoints
7. **Permissions** - Access control
8. **Tests** - Test coverage

---

## Feature Development Process

### Step 1: Define Requirements

**Questions to Answer:**
- What data does the feature need?
- What operations are required?
- Who can access the feature?
- What permissions are needed?
- Are there any business rules?

### Step 2: Create Model

**Model Structure:**
```python
# swx_app/models/feature_name.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from uuid import UUID, uuid4
from datetime import datetime

class FeatureBase(SQLModel):
    # Base fields
    name: str = Field(max_length=255)
    description: str | None = None

class Feature(FeatureBase, Base, table=True):
    __tablename__ = "feature_name"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FeatureCreate(FeatureBase):
    pass

class FeatureUpdate(SQLModel):
    name: str | None = None
    description: str | None = None

class FeaturePublic(FeatureBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True
```

### Step 3: Create Migration

**Generate Migration:**
```bash
# Generate migration
alembic revision --autogenerate -m "Add feature_name table"

# Review migration file
# migrations/versions/xxxx_add_feature_name_table.py

# Apply migration
alembic upgrade head
```

### Step 4: Create Repository

**Repository Pattern:**
```python
# swx_app/repositories/feature_repository.py
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.feature_name import Feature, FeatureCreate, FeatureUpdate

async def get_feature_by_id(session: AsyncSession, feature_id: UUID) -> Feature | None:
    stmt = select(Feature).where(Feature.id == feature_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_all_features(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Feature]:
    stmt = select(Feature).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def create_feature(session: AsyncSession, feature_in: FeatureCreate) -> Feature:
    feature = Feature(**feature_in.model_dump())
    session.add(feature)
    await session.commit()
    await session.refresh(feature)
    return feature

async def update_feature(session: AsyncSession, feature: Feature, feature_in: FeatureUpdate) -> Feature:
    update_data = feature_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feature, field, value)
    session.add(feature)
    await session.commit()
    await session.refresh(feature)
    return feature

async def delete_feature(session: AsyncSession, feature: Feature) -> None:
    await session.delete(feature)
    await session.commit()
```

### Step 5: Create Service

**Service Pattern:**
```python
# swx_app/services/feature_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.feature_name import Feature, FeatureCreate, FeatureUpdate
from swx_app.repositories.feature_repository import (
    get_feature_by_id,
    get_all_features,
    create_feature,
    update_feature,
    delete_feature,
)
from fastapi import HTTPException

async def get_feature_service(session: AsyncSession, feature_id: UUID) -> Feature:
    feature = await get_feature_by_id(session, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature

async def list_features_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Feature]:
    return await get_all_features(session, skip, limit)

async def create_feature_service(session: AsyncSession, feature_in: FeatureCreate) -> Feature:
    return await create_feature(session, feature_in)

async def update_feature_service(
    session: AsyncSession, feature_id: UUID, feature_in: FeatureUpdate
) -> Feature:
    feature = await get_feature_by_id(session, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return await update_feature(session, feature, feature_in)

async def delete_feature_service(session: AsyncSession, feature_id: UUID) -> None:
    feature = await get_feature_by_id(session, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    await delete_feature(session, feature)
```

### Step 6: Create Controller

**Controller Pattern:**
```python
# swx_app/controllers/feature_controller.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.feature_name import Feature, FeatureCreate, FeatureUpdate
from swx_app.services.feature_service import (
    get_feature_service,
    list_features_service,
    create_feature_service,
    update_feature_service,
    delete_feature_service,
)

async def get_feature_controller(session: AsyncSession, feature_id: UUID) -> Feature:
    return await get_feature_service(session, feature_id)

async def list_features_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Feature]:
    return await list_features_service(session, skip, limit)

async def create_feature_controller(session: AsyncSession, feature_in: FeatureCreate) -> Feature:
    return await create_feature_service(session, feature_in)

async def update_feature_controller(
    session: AsyncSession, feature_id: UUID, feature_in: FeatureUpdate
) -> Feature:
    return await update_feature_service(session, feature_id, feature_in)

async def delete_feature_controller(session: AsyncSession, feature_id: UUID) -> None:
    await delete_feature_service(session, feature_id)
```

### Step 7: Create Routes

**Option 1: Use CLI Generator (Recommended)**

The `swx make:resource` command generates routes with authentication included by default:

```bash
swx make:resource feature
```

**Generated routes include:**
- ✅ `UserDep` authentication on all routes
- ✅ Basic CRUD operations
- ✅ Pagination support
- ✅ Type hints and documentation

**After generation, add RBAC or policies:**
```python
# swx_app/routes/feature_route.py
from swx_core.rbac.dependencies import require_permission
from swx_core.services.policy.dependencies import require_policy

@router.get("/", response_model=list[FeaturePublic])
async def list_features(
    session: SessionDep,
    current_user: UserDep,  # ✅ Already included by CLI
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _permission: None = Depends(require_permission("feature:read")),  # Add RBAC
):
    """List all features."""
    return await feature_controller.list_features_controller(session, skip, limit)
```

**Option 2: Manual Route Creation**

**Route Pattern:**
```python
# swx_app/routes/feature_route.py
from fastapi import APIRouter, Depends, Query
from uuid import UUID
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
from swx_core.rbac.dependencies import require_permission
from swx_app.models.feature_name import Feature, FeatureCreate, FeatureUpdate, FeaturePublic
from swx_app.controllers import feature_controller

router = APIRouter(prefix="/feature", tags=["feature"])

@router.get("/", response_model=list[FeaturePublic])
async def list_features(
    session: SessionDep,
    current_user: UserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _permission: None = Depends(require_permission("feature:read")),
):
    """List all features."""
    return await feature_controller.list_features_controller(session, skip, limit)

@router.get("/{feature_id}", response_model=FeaturePublic)
async def get_feature(
    feature_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    _permission: None = Depends(require_permission("feature:read")),
):
    """Get feature by ID."""
    return await feature_controller.get_feature_controller(session, feature_id)

@router.post("/", response_model=FeaturePublic, status_code=201)
async def create_feature(
    feature_in: FeatureCreate,
    session: SessionDep,
    current_user: UserDep,
    _permission: None = Depends(require_permission("feature:write")),
):
    """Create new feature."""
    return await feature_controller.create_feature_controller(session, feature_in)

@router.patch("/{feature_id}", response_model=FeaturePublic)
async def update_feature(
    feature_id: UUID,
    feature_in: FeatureUpdate,
    session: SessionDep,
    current_user: UserDep,
    _permission: None = Depends(require_permission("feature:write")),
):
    """Update feature."""
    return await feature_controller.update_feature_controller(session, feature_id, feature_in)

@router.delete("/{feature_id}", status_code=204)
async def delete_feature(
    feature_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    _permission: None = Depends(require_permission("feature:delete")),
):
    """Delete feature."""
    await feature_controller.delete_feature_controller(session, feature_id)
```

**Note:** CLI-generated routes include `UserDep` authentication by default. You should add RBAC permissions or policies after generation for production use.

### Step 8: Add Permissions

**Seed Permissions:**
```python
# scripts/seed_system.py
permissions = [
    {"name": "feature:read", "description": "Read features"},
    {"name": "feature:write", "description": "Create and update features"},
    {"name": "feature:delete", "description": "Delete features"},
]
```

---

## Complete Example

### Product Feature

**Model:**
```python
# swx_app/models/product.py
class Product(Base, table=True):
    __tablename__ = "product"
    id: UUID
    name: str
    price: float
    created_at: datetime
```

**Repository:**
```python
# swx_app/repositories/product_repository.py
async def get_product_by_id(session: AsyncSession, product_id: UUID) -> Product | None:
    ...
```

**Service:**
```python
# swx_app/services/product_service.py
async def get_product_service(session: AsyncSession, product_id: UUID) -> Product:
    ...
```

**Controller:**
```python
# swx_app/controllers/product_controller.py
async def get_product_controller(session: AsyncSession, product_id: UUID) -> Product:
    ...
```

**Routes:**
```python
# swx_app/routes/product_route.py
@router.get("/{product_id}")
async def get_product(product_id: UUID, session: SessionDep, user: UserDep):
    ...
```

---

## Adding Permissions

### Permission Naming

**Standard Pattern:**
- `{resource}:read` - Read access
- `{resource}:write` - Write access
- `{resource}:delete` - Delete access

**Examples:**
- `product:read`
- `product:write`
- `product:delete`

### Seeding Permissions

**Add to Seed Script:**
```python
# scripts/seed_system.py
permissions = [
    {"name": "product:read", "description": "Read products"},
    {"name": "product:write", "description": "Create and update products"},
    {"name": "product:delete", "description": "Delete products"},
]
```

### Using Permissions

**In Routes:**
```python
from swx_core.rbac.dependencies import require_permission

@router.get("/", dependencies=[Depends(require_permission("product:read"))])
async def list_products():
    ...
```

---

## Adding Routes

### Route Organization

**User Routes:**
- `/api/user/feature/` - User-accessible features

**Admin Routes:**
- `/api/admin/feature/` - Admin-only features

### Route Registration

**Automatic Discovery:**
- Routes in `swx_app/routes/` automatically discovered
- No manual registration needed

**Export Route:**
```python
# swx_app/routes/__init__.py
from swx_app.routes.feature_route import router as feature_router

__all__ = ["feature_router"]
```

---

## Testing Features

### Unit Tests

**Test Repository:**
```python
# swx_app/tests/test_feature_repository.py
async def test_get_feature_by_id():
    feature = await get_feature_by_id(session, feature_id)
    assert feature is not None
```

**Test Service:**
```python
# swx_app/tests/test_feature_service.py
async def test_get_feature_service():
    feature = await get_feature_service(session, feature_id)
    assert feature is not None
```

### Integration Tests

**Test Routes:**
```python
# swx_app/tests/test_feature_routes.py
async def test_list_features(client, token):
    response = client.get("/api/feature/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
```

---

## Best Practices

### ✅ DO

1. **Follow layered architecture**
   ```python
   # ✅ Good - Layered
   Route → Controller → Service → Repository → Model
   ```

2. **Use type hints**
   ```python
   # ✅ Good - Type hints
   async def get_feature(feature_id: UUID) -> Feature:
       ...
   ```

3. **Protect with permissions**
   ```python
   # ✅ Good - Permission check
   @router.get("/", dependencies=[Depends(require_permission("feature:read"))])
   ```

4. **Handle errors**
   ```python
   # ✅ Good - Error handling
   if not feature:
       raise HTTPException(status_code=404, detail="Feature not found")
   ```

5. **Write tests**
   ```python
   # ✅ Good - Tests
   async def test_get_feature():
       ...
   ```

### ❌ DON'T

1. **Don't bypass layers**
   ```python
   # ❌ Bad - Bypassing layers
   @router.get("/")
   async def get_features(session: SessionDep):
       stmt = select(Feature)  # Direct database access
   ```

2. **Don't skip permissions**
   ```python
   # ❌ Bad - No permission check
   @router.delete("/{id}")
   async def delete_feature(id: UUID):
       ...
   ```

3. **Don't modify framework code**
   ```python
   # ❌ Bad - Modifying framework
   # swx_core/models/user.py - DON'T MODIFY
   ```

---

## Next Steps

- Read [Adding Entitlements](./ADDING_ENTITLEMENTS.md) for billing integration
- Read [Adding Policies](./ADDING_POLICIES.md) for policy creation
- Read [Custom Models](./CUSTOM_MODELS.md) for model patterns

---

**Status:** Adding features guide documented, ready for implementation.
