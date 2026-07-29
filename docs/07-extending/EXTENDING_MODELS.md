# Extending Models

**Version:** 2.9.0
**Last Updated:** 2026-07-23

---

## Table of Contents

1. [Overview](#overview)
2. [Framework Tables](#framework-tables)
3. [Pattern 1: One-to-One Profile Extension](#pattern-1-one-to-one-profile-extension)
4. [Pattern 2: Composition with Mixins](#pattern-2-composition-with-mixins)
5. [Pattern 3: Feature Registry Extension](#pattern-3-feature-registry-extension)
6. [Pattern 4: CLI Resource Scaffolding](#pattern-4-cli-resource-scaffolding)
7. [Pattern 5: Base Class Pattern (CRUD)](#pattern-5-base-class-pattern-crud)
8. [Pattern 6: Service Layer Extension](#pattern-6-service-layer-extension)
9. [Pattern Comparison](#pattern-comparison)
10. [Best Practices](#best-practices)
11. [Migration Guide](#migration-guide)

---

## Overview

SwX-API keeps **framework code** (`swx_core/`) separate from **application code** (`swx_app/`). Do not add columns directly to framework tables; use one of the extension patterns instead.

### Key Principle

> **Never modify `swx_core/` tables.** Extend them through profile tables, mixins, the feature registry, or application-level models.

### When to Use Each Pattern

| You Want To | Use Pattern |
|---|---|
| Add fields to a user (bio, avatar, phone) | Pattern 1: Profile Extension |
| Create a new model with common fields (id, timestamps, soft delete) | Pattern 2: Mixins |
| Add a new billable feature or entitlement | Pattern 3: Feature Registry |
| Scaffold a complete CRUD resource | Pattern 4: CLI Scaffolding |
| Build a CRUD API with minimal boilerplate | Pattern 5: Base Classes |
| Extend a core service with custom logic | Pattern 6: Service Extension |

---

## Framework Tables

These SwX-managed tables must not be modified directly:

| Table | Purpose |
|---|---|
| `swx_users` | User accounts |
| `swx_admin_user` | Admin accounts |
| `swx_role` | Role definitions |
| `swx_permission` | Permission definitions |
| `swx_user_role` | User-role assignments |
| `swx_role_permission` | Role-permission mappings |
| `swx_team` | Team definitions |
| `swx_team_member` | Team memberships |
| `swx_audit_log` | Audit logs |
| `swx_job` | Background jobs |
| `swx_language` | Translations |
| `swx_refresh_token` | Refresh tokens |
| `swx_policy` | ABAC policies |
| `swx_system_config` | Runtime settings |
| `swx_billing_*` | Billing tables |

To add related data, use a **profile extension table** (Pattern 1).

---

## Pattern 1: One-to-One Profile Extension

**Use when:** You need to add custom fields to an existing framework entity (User, Admin, Team).

### How It Works

Create a new table with a **unique foreign key** to the framework table. This gives you a 1:1 relationship without modifying the original table.

### Step-by-Step

#### 1. Create the Profile Model

```python
# swx_app/models/user_profile.py
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime
from swx_core.utils.time import utc_now

class UserProfileBase(SQLModel):
    """Fields visible in API responses and creation."""
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferences: dict = Field(default_factory=dict)

class UserProfile(UserProfileBase, table=True):
    __tablename__ = "user_profile"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        foreign_key="swx_users.id",
        unique=True,
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

class UserProfileCreate(UserProfileBase):
    pass

class UserProfileUpdate(SQLModel):
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferences: Optional[dict] = None

class UserProfilePublic(UserProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

> **Important:** Always use `foreign_key="swx_users.id"` — note the `swx_` prefix on framework tables.

#### 2. Export the Model

```python
# swx_app/models/__init__.py
from swx_app.models.user_profile import (
    UserProfile,
    UserProfileCreate,
    UserProfileUpdate,
    UserProfilePublic,
)

__all__ = [
    "UserProfile",
    "UserProfileCreate",
    "UserProfileUpdate",
    "UserProfilePublic",
]
```

#### 3. Generate the Migration

```bash
swx db revision --autogenerate -m "add_user_profile_table"
```

Review the generated migration file, then apply it:

```bash
swx db migrate
```

#### 4. Create Repository

```python
# swx_app/repositories/user_profile_repository.py
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.models.user_profile import UserProfile

async def get_profile_by_user_id(
    session: AsyncSession, user_id: UUID
) -> UserProfile | None:
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_profile(
    session: AsyncSession, profile: UserProfile
) -> UserProfile:
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile

async def update_profile(
    session: AsyncSession, profile: UserProfile, data: dict
) -> UserProfile:
    for key, value in data.items():
        setattr(profile, key, value)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile
```

#### 5. Create Service

```python
# swx_app/services/user_profile_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi import HTTPException
from swx_app.models.user_profile import (
    UserProfile, UserProfileCreate, UserProfileUpdate,
)
from swx_app.repositories.user_profile_repository import (
    get_profile_by_user_id, create_profile, update_profile,
)

async def get_or_create_profile(
    session: AsyncSession, user_id: UUID
) -> UserProfile:
    profile = await get_profile_by_user_id(session, user_id)
    if not profile:
        profile = UserProfile(user_id=user_id)
        profile = await create_profile(session, profile)
    return profile

async def update_user_profile(
    session: AsyncSession, user_id: UUID, data: UserProfileUpdate
) -> UserProfile:
    profile = await get_profile_by_user_id(session, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return await update_profile(session, profile, data.model_dump(exclude_unset=True))
```

#### 6. Create Controller

```python
# swx_app/controllers/user_profile_controller.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_app.services.user_profile_service import (
    get_or_create_profile, update_user_profile,
)
from swx_app.models.user_profile import UserProfilePublic, UserProfileUpdate

async def get_profile(session: AsyncSession, user_id: UUID) -> UserProfilePublic:
    profile = await get_or_create_profile(session, user_id)
    return UserProfilePublic.model_validate(profile)

async def patch_profile(
    session: AsyncSession, user_id: UUID, data: UserProfileUpdate
) -> UserProfilePublic:
    profile = await update_user_profile(session, user_id, data)
    return UserProfilePublic.model_validate(profile)
```

#### 7. Create Routes

```python
# swx_app/routes/user_profile_route.py
from fastapi import APIRouter, Depends
from uuid import UUID
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
from swx_core.rbac.dependencies import require_permission
from swx_app.models.user_profile import UserProfilePublic, UserProfileUpdate
from swx_app.controllers import user_profile_controller

router = APIRouter(prefix="/user/profile", tags=["user-profile"])

@router.get("/", response_model=UserProfilePublic)
async def get_my_profile(
    session: SessionDep,
    current_user: UserDep,
):
    """Get or create the current user's profile."""
    return await user_profile_controller.get_profile(session, current_user.id)

@router.patch("/", response_model=UserProfilePublic)
async def update_my_profile(
    data: UserProfileUpdate,
    session: SessionDep,
    current_user: UserDep,
    _perm: None = Depends(require_permission("profile:write")),
):
    """Update the current user's profile."""
    return await user_profile_controller.patch_profile(
        session, current_user.id, data
    )

@router.get("/{user_id}", response_model=UserProfilePublic)
async def get_user_profile(
    user_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    _perm: None = Depends(require_permission("profile:read")),
):
    """Get another user's profile (admin)."""
    return await user_profile_controller.get_profile(session, user_id)
```

#### 8. Export Route

```python
# swx_app/routes/__init__.py
from swx_app.routes.user_profile_route import router as user_profile_router

__all__ = ["user_profile_router"]
```

### Admin Profile Extension

Use the same pattern for admin users with `swx_admin_user.id`:

```python
class AdminProfile(SQLModel, table=True):
    __tablename__ = "admin_profile"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    admin_id: UUID = Field(
        foreign_key="swx_admin_user.id",
        unique=True,
        index=True,
    )
    department: Optional[str] = None
    office_location: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
```

### Composition Pattern (Combining User + Profile)

For endpoints that need both User and Profile data, use a composite response schema:

```python
# swx_app/models/user_profile.py
class UserWithProfile(SQLModel):
    """Composite schema combining User and UserProfile."""
    id: UUID
    email: str
    full_name: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True
```

Then in your service, fetch both and merge:

```python
from swx_core.services.user_service import get_user_by_id
from swx_app.repositories.user_profile_repository import get_profile_by_user_id

async def get_user_with_profile(session: AsyncSession, user_id: UUID) -> dict:
    user = await get_user_by_id(session, user_id)
    profile = await get_profile_by_user_id(session, user_id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "bio": profile.bio if profile else None,
        "avatar_url": profile.avatar_url if profile else None,
        "phone": profile.phone if profile else None,
    }
```

---

## Pattern 2: Composition with Mixins

**Use when:** Creating new models that share common fields like timestamps, soft delete, or audit trails.

### Available Mixins

| Mixin | Fields Provided | Use Case |
|---|---|---|
| `TimestampMixin` | `created_at`, `updated_at` | Any model needing timestamps |
| `SoftDeleteMixin` | `is_deleted`, `deleted_at` + `soft_delete()` / `restore()` | Models supporting soft delete |
| `UUIDPrimaryKeyMixin` | `id: UUID` | Models needing UUID primary keys |
| `ActiveMixin` | `is_active` + `activate()` / `deactivate()` | Models needing active/inactive toggle |
| `SlugMixin` | `slug` (unique, indexed) | Models needing URL-friendly identifiers |
| `TitleMixin` | `title` (indexed, max 255) | Models needing a title field |
| `DescriptionMixin` | `description` (optional) | Models needing a description |
| `MetadataMixin` | `metadata` (JSON dict) | Models needing flexible metadata |
| `CreatedByMixin` | `created_by_id` | Models tracking who created them |
| `UpdatedByMixin` | `updated_by_id` | Models tracking who last updated them |
| `AuditMixin` | `created_at`, `updated_at`, `created_by_id`, `updated_by_id` | Full audit trail |
| `FullModelMixin` | `id`, `created_at`, `updated_at`, `is_active` | Standard model with UUID + timestamps + active |
| `AuditedModelMixin` | `id`, `created_at`, `updated_at`, `is_active`, `created_by_id`, `updated_by_id` | Full model with audit tracking |

### Basic Usage

```python
from swx_core.utils.mixins import FullModelMixin
from sqlmodel import Field
from typing import Optional

class Product(FullModelMixin, table=True):
    __tablename__ = "product"

    name: str = Field(max_length=255, index=True)
    price: float = Field(ge=0)
    description: Optional[str] = None
```

This gives `Product` an `id` (UUID), `created_at`, `updated_at`, and `is_active` field without extra boilerplate.

### Combining Mixins

Compose mixins to include only the fields you need:

```python
from swx_core.utils.mixins import (
    UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, CreatedByMixin
)

class Order(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "order"

    total: float = Field(ge=0)
    status: str = Field(default="pending", max_length=50)
```

This gives `Order`: `id`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`.

### With Audit Trail

```python
from swx_core.utils.mixins import AuditedModelMixin

class AuditLog(AuditedModelMixin, table=True):
    __tablename__ = "app_audit_log"

    action: str = Field(max_length=100)
    resource_type: str = Field(max_length=50)
    resource_id: str = Field(max_length=36)
    details: dict = Field(default_factory=dict)
```

This gives `AuditLog`: `id`, `created_at`, `updated_at`, `is_active`, `created_by_id`, `updated_by_id`.

### Soft Delete Pattern

When using `SoftDeleteMixin`, use the helper methods and filter deleted records:

```python
from swx_core.utils.mixins import FullModelMixin
from sqlmodel import select

# Soft delete a record
product.soft_delete()

# Restore a soft-deleted record
product.restore()

# Query only active (non-deleted) records
stmt = select(Product).where(Product.is_deleted == False)
```

### Slug Pattern

```python
from swx_core.utils.mixins import SlugMixin, TimestampMixin

class Article(SlugMixin, TimestampMixin, table=True):
    __tablename__ = "article"

    # slug field is automatically provided
    title: str = Field(max_length=255)
    content: str

# Generate slug before insert
article = Article(slug="my-first-article", title="My First Article", content="...")
```

---

## Pattern 3: Feature Registry Extension

**Use when:** Adding new billable features, entitlements, or feature flags to the billing system.

### How It Works

The `FeatureRegistry` centralizes features gated by billing plans. Register each `FeatureDefinition` with a unique key, and it becomes available for entitlement checks.

### Registering a Feature

```python
# swx_app/features.py (or in your app startup)
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureDefinition
from swx_core.models.billing import FeatureType

# Register a boolean feature (on/off)
FeatureRegistry.register(FeatureDefinition(
    key="custom.branding",
    name="Custom Branding",
    description="Ability to customize the application's branding and theme.",
    feature_type=FeatureType.BOOLEAN,
))

# Register a quota feature (with units)
FeatureRegistry.register(FeatureDefinition(
    key="storage.gb",
    name="Storage",
    description="Cloud storage allocation in gigabytes.",
    feature_type=FeatureType.QUOTA,
    unit="GB",
))

# Register a metered feature (usage-based)
FeatureRegistry.register(FeatureDefinition(
    key="api.calls",
    name="API Calls",
    description="Number of API requests allowed per billing period.",
    feature_type=FeatureType.METERED,
    unit="requests",
))
```

### Checking Feature Access

```python
from swx_core.services.billing.feature_registry import FeatureRegistry

# Get a feature definition
feature = FeatureRegistry.get("custom.branding")
if feature:
    print(f"{feature.name}: {feature.description}")

# List all registered features
all_features = FeatureRegistry.list_all()
for f in all_features:
    print(f"{f.key} ({f.feature_type.value})")
```

### Feature Types

| Type | Description | Example |
|---|---|---|
| `BOOLEAN` | Simple on/off feature | `"white_labeling"`, `"advanced.analytics"` |
| `QUOTA` | Numeric limit with units | `"team.members"` (members), `"storage.gb"` (GB) |
| `METERED` | Usage-based counting | `"api.calls"` (requests), `"llm.tokens"` (tokens) |

### Where to Register Features

Keep application features in a dedicated module:

```python
# swx_app/features.py
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureDefinition
from swx_core.models.billing import FeatureType

def register_app_features():
    """Register all application-specific features."""
    FeatureRegistry.register(FeatureDefinition(
        key="document.export",
        name="Document Export",
        description="Export documents to PDF and other formats.",
        feature_type=FeatureType.BOOLEAN,
    ))

    FeatureRegistry.register(FeatureDefinition(
        key="storage.gb",
        name="Storage",
        description="Cloud storage allocation in gigabytes.",
        feature_type=FeatureType.QUOTA,
        unit="GB",
    ))
```

Then call it during app startup:

```python
# swx_app/__init__.py or swx_core/main.py
from swx_app.features import register_app_features

register_app_features()
```

### Integration with Entitlements

Feature definitions work with the billing entitlement system. See [Adding Entitlements](./ADDING_ENTITLEMENTS.md) for the full entitlement flow.

---

## Pattern 4: CLI Resource Scaffolding

**Use when:** You need a complete CRUD resource (model, repository, service, controller, routes) generated automatically.

### Basic Scaffold

```bash
swx make:resource Product
```

This generates:
- `swx_app/models/product.py` — Model with Base, Create, Update, Public schemas
- `swx_app/repositories/product_repository.py` — CRUD repository functions
- `swx_app/services/product_service.py` — Business logic layer
- `swx_app/controllers/product_controller.py` — Request handling
- `swx_app/routes/product_route.py` — REST endpoints with `UserDep` auth

### Base Class Scaffold (Recommended for v2.0+)

```bash
swx make:resource Product --base
```

This generates resources using `BaseRepository`, `BaseService`, and `BaseController` — reducing boilerplate by ~80%:

```python
# Generated with --base
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
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
        )
        self.register_routes()
```

### Custom Fields

You can specify fields during scaffolding:

```bash
swx make:resource Product --fields "name:string price:float is_active:boolean"
```

### After Scaffolding

1. **Review generated code** — Adjust field names, add validation
2. **Add RBAC permissions** — Add `require_permission()` to routes
3. **Add business logic** — Extend service methods
4. **Generate migration** — `swx db revision --autogenerate -m "add_product_table"`
5. **Apply migration** — `swx db migrate`

---

## Pattern 5: Base Class Pattern (CRUD)

**Use when:** You want CRUD operations with minimal code via `BaseRepository`, `BaseService`, and `BaseController`.

### BaseRepository

Provides: `find_by_id`, `find_all`, `find_by`, `create`, `update`, `delete`, `search`, `paginate`, `count`, `exists_by`, `soft_delete`.

```python
from swx_core.repositories.base import BaseRepository
from swx_app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)

    # Add custom queries
    async def find_by_sku(self, sku: str) -> Product | None:
        return await self.find_by_field("sku", sku)

    async def find_active(self, skip: int = 0, limit: int = 100) -> list[Product]:
        return await self.find_by(is_active=True, skip=skip, limit=limit)
```

### BaseService

Provides: `get`, `create`, `update`, `delete`, `list`, `search`, and event hooks (`before_create`, `after_create`, etc.).

```python
from swx_core.services.base import BaseService
from swx_app.models.product import Product
from swx_app.repositories.product_repository import ProductRepository

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())

    # Override hooks for custom logic
    async def before_create(self, data: dict) -> dict:
        # Add validation, defaults, computed fields
        if "sku" not in data:
            data["sku"] = data["name"].lower().replace(" ", "-")
        return data

    async def after_create(self, record: Product, data: dict) -> None:
        # Send notifications, update search index, etc.
        pass
```

### BaseController

Provides: `list`, `get`, `get_by`, `create`, `update`, and `delete` endpoints with automatic route registration.

```python
from swx_core.controllers.base import BaseController
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic

class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
            tags=["Products"],
        )
        self.register_routes()
```

### Full Example with All Layers

```python
# swx_app/models/product.py
from sqlmodel import SQLModel, Field
from swx_core.utils.mixins import FullModelMixin
from typing import Optional

class ProductBase(SQLModel):
    name: str = Field(max_length=255, index=True)
    price: float = Field(ge=0)
    description: Optional[str] = None

class Product(ProductBase, FullModelMixin, table=True):
    __tablename__ = "product"

class ProductCreate(ProductBase):
    pass

class ProductUpdate(SQLModel):
    name: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None

class ProductPublic(ProductBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# swx_app/repositories/product_repository.py
from swx_core.repositories.base import BaseRepository
from swx_app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)

# swx_app/services/product_service.py
from swx_core.services.base import BaseService
from swx_app.models.product import Product
from swx_app.repositories.product_repository import ProductRepository

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())

# swx_app/controllers/product_controller.py
from swx_core.controllers.base import BaseController
from swx_app.models.product import (
    Product, ProductCreate, ProductUpdate, ProductPublic
)

class ProductController(
    BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]
):
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

## Pattern 6: Service Layer Extension

**Use when:** You want to extend a core framework service with custom business logic without changing framework code.

### Extending Core Services

```python
# swx_app/services/extended_user_service.py
from swx_core.services.user_service import UserService as CoreUserService
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class ExtendedUserService(CoreUserService):
    """Extends the core UserService with profile management."""

    async def get_user_with_profile(
        self, session: AsyncSession, user_id: UUID
    ) -> dict:
        """Get user data merged with their profile."""
        user = await self.get(session, user_id)
        from swx_app.repositories.user_profile_repository import get_profile_by_user_id
        profile = await get_profile_by_user_id(session, user_id)

        result = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        }
        if profile:
            result.update({
                "bio": profile.bio,
                "avatar_url": profile.avatar_url,
                "phone": profile.phone,
            })
        return result
```

### Composing Services

Instead of inheriting, you can compose services for more flexibility:

```python
# swx_app/services/user_profile_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from swx_core.services.user_service import get_user_by_id
from swx_app.repositories.user_profile_repository import get_profile_by_user_id

async def get_user_with_profile(session: AsyncSession, user_id: UUID) -> dict:
    """Compose user + profile data from separate services."""
    user = await get_user_by_id(session, user_id)
    profile = await get_profile_by_user_id(session, user_id)

    result = {"id": user.id, "email": user.email, "full_name": user.full_name}
    if profile:
        result.update({
            "bio": profile.bio,
            "avatar_url": profile.avatar_url,
        })
    return result
```

### Hooking into Core Events

Listen to framework events to add custom behavior:

```python
# swx_app/event_handlers.py
from swx_core.events import event_bus, Event

async def on_user_registered(event: Event):
    """Create a default profile when a user registers."""
    user_id = event.payload.get("user_id")
    # Create profile, send welcome email, etc.

async def on_user_deleted(event: Event):
    """Clean up profile when a user is deleted."""
    user_id = event.payload.get("user_id")
    # Delete profile, clean up related data

# Register handlers during app startup
event_bus.listen("user.registered", on_user_registered)
event_bus.listen("user.deleted", on_user_deleted)
```

---

## Pattern Comparison

| Pattern | Best For | Coupling | Complexity | Migrations |
|---|---|---|---|---|
| Profile Extension | Adding fields to User/Admin | Low (FK reference) | Medium | Yes |
| Mixins | New models with common fields | None | Low | Yes |
| Feature Registry | Billable features/flags | Low (registration) | Low | No |
| CLI Scaffolding | Quick CRUD resources | Low (generated) | Low | Yes |
| Base Classes | CRUD with minimal boilerplate | Low (inheritance) | Low | Yes |
| Service Extension | Custom business logic | Medium (inheritance/composition) | Medium | Maybe |

---

## Best Practices

### Do

1. **Use profile tables** for extending framework entities — never modify `swx_*` tables directly
2. **Use mixins** for common model fields — avoid duplication across models
3. **Use `foreign_key="swx_users.id"`** — always reference framework tables with the `swx_` prefix
4. **Keep models under 200 lines** — split into separate files when needed
5. **Follow the layered architecture** — Route → Controller → Service → Repository → Model
6. **Register features at startup** — use a dedicated `features.py` module
7. **Use `--base` flag** with `swx make:resource` for modern patterns
8. **Create migrations** — always review and test auto-generated migrations
9. **Export models** in `__init__.py` — ensures automatic discovery
10. **Export routes** in `__init__.py` — ensures automatic registration

### Don't

1. **Don't add columns to `swx_*` tables** — use profile extension tables instead
2. **Don't bypass the layered architecture** — always go through all layers
3. **Don't import from `swx_core` internals** — use public APIs and dependencies
4. **Don't skip migrations** — always generate and review schema changes
5. **Don't forget `unique=True`** on profile FK columns — ensures 1:1 relationship
6. **Don't forget `index=True`** on FK columns — ensures query performance
7. **Don't hard-code feature keys** — register them in the FeatureRegistry

---

## Migration Guide

### Adding a Profile Extension to Existing Users

```bash
# 1. Create the model (see Pattern 1)
# 2. Generate migration
swx db revision --autogenerate -m "add_user_profile_table"

# 3. Review the generated migration
# Check: user_profile.user_id has unique=True and foreign_key to swx_users.id

# 4. Apply migration
swx db migrate

# 5. (Optional) Seed profiles for existing users
python scripts/seed_profiles.py
```

### Adding Mixin Fields to Existing Models

```bash
# 1. Add the mixin to your model class
# 2. Generate migration
swx db revision --autogenerate -m "add_soft_delete_to_product"

# 3. Review: ensure nullable/defaults for existing rows
# Example: is_deleted should default to False
# Example: deleted_at should be nullable

# 4. Apply migration
swx db migrate
```

### Registering New Features

No migration needed — feature definitions are registered in code:

```python
# swx_app/features.py
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureDefinition
from swx_core.models.billing import FeatureType

FeatureRegistry.register(FeatureDefinition(
    key="document.export",
    name="Document Export",
    description="Export documents to PDF and other formats.",
    feature_type=FeatureType.BOOLEAN,
))
```

---

## Next Steps

- Read [Custom Models](./CUSTOM_MODELS.md) for detailed model patterns
- Read [Adding Features](./ADDING_FEATURES.md) for feature development workflow
- Read [Adding Entitlements](./ADDING_ENTITLEMENTS.md) for billing integration
- Read [Base Classes](../04-core-concepts/BASE_CLASSES.md) for the base class API reference
- Read [Architecture](../03-architecture/ARCHITECTURE.md) for system design overview

---

**Status:** Extending models guide documented and ready for use.
