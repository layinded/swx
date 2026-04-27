# Custom Models

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Model Structure](#model-structure)
3. [Base Model](#base-model)
4. [Model Patterns](#model-patterns)
5. [Relationships](#relationships)
6. [Migrations](#migrations)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API uses **SQLModel** for database models, combining SQLAlchemy and Pydantic. This guide covers how to create custom models that integrate with the framework.

### Key Principles

1. **Inherit from Base** - Use `swx_core.models.base.Base`
2. **Use SQLModel** - Combine database and API models
3. **Automatic Discovery** - Models automatically registered
4. **Type Safety** - Use type hints throughout
5. **Follow Patterns** - Use established patterns

---

## Model Structure

### Standard Model Pattern

**Complete Model:**
```python
# swx_app/models/product.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

# Base fields (shared between create/update/public)
class ProductBase(SQLModel):
    name: str = Field(max_length=255, index=True)
    description: Optional[str] = None
    price: float = Field(ge=0)
    is_active: bool = Field(default=True)

# Database model
class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships (if any)
    # user_id: UUID = Field(foreign_key="user.id")

# Create schema
class ProductCreate(ProductBase):
    pass

# Update schema
class ProductUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

# Public schema (for API responses)
class ProductPublic(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

---

## Base Model

### Using Base

**Inherit from Base:**
```python
from swx_core.models.base import Base

class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    ...
```

**Base Provides:**
- Common fields (if any)
- Framework integration
- Automatic registration

### Model Registration

**Automatic Discovery:**
- Models in `swx_app/models/` automatically discovered
- Models in `swx_core/models/` automatically discovered
- No manual registration needed

**Export Model:**
```python
# swx_app/models/__init__.py
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic

__all__ = ["Product", "ProductCreate", "ProductUpdate", "ProductPublic"]
```

---

## Model Patterns

### Pattern 1: Simple Model

**No Relationships:**
```python
class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern 2: User-Owned Model

**Belongs to User:**
```python
class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    name: str
    price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern 3: Team-Scoped Model

**Belongs to Team:**
```python
class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)  # Creator
    name: str
    price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern 4: Soft Delete

**Soft Delete Support:**
```python
class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    price: float
    is_active: bool = Field(default=True)
    deleted_at: Optional[datetime] = None  # Soft delete
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Relationships

### One-to-Many

**User to Products:**
```python
from sqlmodel import Relationship

class Product(ProductBase, Base, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    
    # Relationship
    user: "User" = Relationship(back_populates="products")

class User(UserBase, Base, table=True):
    # ... user fields ...
    
    # Relationship
    products: list["Product"] = Relationship(back_populates="user")
```

### Many-to-Many

**Products to Tags:**
```python
# Junction table
class ProductTag(Base, table=True):
    __tablename__ = "product_tag"
    product_id: UUID = Field(foreign_key="product.id", primary_key=True)
    tag_id: UUID = Field(foreign_key="tag.id", primary_key=True)

class Product(ProductBase, Base, table=True):
    # ... product fields ...
    
    # Many-to-many relationship
    tags: list["Tag"] = Relationship(
        back_populates="products",
        link_model=ProductTag
    )
```

---

## Migrations

### Generating Migrations

**Autogenerate:**
```bash
# Generate migration
alembic revision --autogenerate -m "Add product table"

# Review migration
# migrations/versions/xxxx_add_product_table.py

# Apply migration
alembic upgrade head
```

### Migration Best Practices

**1. Review Generated Migration:**
```python
# migrations/versions/xxxx_add_product_table.py
def upgrade() -> None:
    op.create_table(
        'product',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_name'), 'product', ['name'], unique=False)
```

**2. Add Indexes:**
```python
# Add indexes for common queries
op.create_index('ix_product_user_id', 'product', ['user_id'])
op.create_index('ix_product_created_at', 'product', ['created_at'])
```

**3. Test Migration:**
```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Verify
alembic current
```

---

## Best Practices

### ✅ DO

1. **Use type hints**
   ```python
   # ✅ Good - Type hints
   name: str = Field(max_length=255)
   price: float = Field(ge=0)
   created_at: datetime = Field(default_factory=datetime.utcnow)
   ```

2. **Use Field constraints**
   ```python
   # ✅ Good - Field constraints
   name: str = Field(max_length=255, index=True)
   price: float = Field(ge=0)  # Greater than or equal to 0
   email: str = Field(regex="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
   ```

3. **Use Optional for nullable fields**
   ```python
   # ✅ Good - Optional for nullable
   description: Optional[str] = None
   deleted_at: Optional[datetime] = None
   ```

4. **Add indexes for queries**
   ```python
   # ✅ Good - Indexed fields
   user_id: UUID = Field(foreign_key="user.id", index=True)
   created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
   ```

5. **Use relationships properly**
   ```python
   # ✅ Good - Proper relationships
   user: "User" = Relationship(back_populates="products")
   ```

### ❌ DON'T

1. **Don't use mutable defaults**
   ```python
   # ❌ Bad - Mutable default
   tags: list[str] = []  # DON'T DO THIS
   
   # ✅ Good - Factory default
   tags: list[str] = Field(default_factory=list)
   ```

2. **Don't skip type hints**
   ```python
   # ❌ Bad - No type hints
   name = Field(max_length=255)
   
   # ✅ Good - Type hints
   name: str = Field(max_length=255)
   ```

3. **Don't forget indexes**
   ```python
   # ❌ Bad - No index
   user_id: UUID = Field(foreign_key="user.id")
   
   # ✅ Good - Indexed
   user_id: UUID = Field(foreign_key="user.id", index=True)
   ```

---

## Extending SwX Framework Tables

SwX framework tables use the `swx_` prefix to differentiate them from user-defined tables. Users should NOT directly modify framework tables. Instead, use one of these patterns:

### Framework Tables (swx_ prefix)

All framework tables are prefixed with `swx_`:
- `swx_users` - User accounts
- `swx_admin_user` - Admin accounts
- `swx_role` - Roles
- `swx_permission` - Permissions
- `swx_team` - Teams
- `swx_user_role` - User-role assignments
- `swx_team_member` - Team memberships
- `swx_role_permission` - Role-permission mappings
- `swx_audit_log` - Audit logs
- `swx_job` - Background jobs
- `swx_language` - Translations
- `swx_refresh_token` - Refresh tokens
- `swx_policy` - ABAC policies
- `swx_system_config` - System settings
- `swx_billing_*` - Billing tables

### Pattern 1: One-to-One Extension (Recommended)

Create a separate table linked to the framework table:

```python
from swx_app/models/user_profile.py
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime

class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="swx_users.id", unique=True, index=True)
    
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    preferences: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern 2: Model Inheritance

Extend a framework model with additional fields:

```python
from swx_app/models/extended_user.py
from swx_core.models.user import User as BaseUser
from sqlmodel import Field
from typing import Optional

class ExtendedUser(BaseUser, table=True):
    __tablename__ = "extended_user"
    
    user_id: UUID = Field(foreign_key="swx_users.id", unique=True)
    custom_field_1: Optional[str] = None
    custom_field_2: Optional[int] = None
```

### Pattern 3: Composition via Service Layer

Add business logic without modifying tables:

```python
from swx_app/services/user_service.py
from swx_core.services.user_service import UserService as CoreUserService

class ExtendedUserService(CoreUserService):
    async def get_user_with_profile(self, db, user_id: UUID) -> dict:
        user = await self.get(db, user_id)
        profile = await self.get_profile(db, user_id)
        return {**user.model_dump(), "profile": profile}
    
    async def get_profile(self, db, user_id: UUID):
        return await db.exec(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).first()
```

### Pattern 4: Using Custom Mixins

Create user tables using framework mixins:

```python
from swx_core.utils.mixins import FullModelMixin, AuditedModelMixin
from sqlmodel import Field
from typing import Optional

class Product(FullModelMixin, table=True):
    __tablename__ = "product"
    
    name: str = Field(max_length=255, index=True)
    price: float = Field(gt=0)
    description: Optional[str] = None
```

### Available Mixins

| Mixin | Fields Provided |
|-------|-----------------|
| `TimestampMixin` | `created_at`, `updated_at` |
| `SoftDeleteMixin` | `is_deleted`, `deleted_at` |
| `UUIDPrimaryKeyMixin` | `id: UUID` |
| `CreatedByMixin` | `created_by_id` |
| `UpdatedByMixin` | `updated_by_id` |
| `FullModelMixin` | UUID + Timestamps + SoftDelete |
| `AuditedModelMixin` | FullModel + CreatedBy + UpdatedBy |

### Foreign Key References to Framework Tables

Always reference framework tables with the `swx_` prefix:

```python
class Order(SQLModel, table=True):
    __tablename__ = "order"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="swx_users.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)
    total: float
```

### Migration for Extending Users

If you need to add columns to track additional user data, create a new table rather than modifying `swx_users`:

1. Create a model with foreign key to `swx_users.id`
2. Generate migration: `swx db revision -m "add_user_profile"`
3. Apply migration: `swx db migrate`

This approach keeps framework tables isolated and allows upgrades without data loss.

---

## Next Steps

- Read [Adding Features](./ADDING_FEATURES.md) for feature development
- Read [Extending Guide](./EXTENDING_SWX.md) for extension patterns
- Read [Architecture Documentation](../03-architecture/ARCHITECTURE.md) for system design

---

**Status:** Custom models guide documented, ready for implementation.
