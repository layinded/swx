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

## Next Steps

- Read [Adding Features](./ADDING_FEATURES.md) for feature development
- Read [Extending Guide](./EXTENDING_SWX.md) for extension patterns
- Read [Architecture Documentation](../03-architecture/ARCHITECTURE.md) for system design

---

**Status:** Custom models guide documented, ready for implementation.
