# Multi-Tenant Support

SwX-Core v2.7.22+ provides comprehensive multi-tenant support through context-aware repositories, controllers, and middleware.

---

## Overview

Multi-tenant SaaS applications require automatic data isolation between tenants. SwX-Core provides:

- **TenantAwareRepository** - Automatic tenant filtering on all queries
- **TenantContextMiddleware** - Request-scoped tenant context extraction
- **TenantAwareController** - Automatic tenant injection on create operations
- **EntitlementService** - Quota enforcement and feature gating
- **PostgreSQL RLS** - Database-level security layer

---

## Quick Start

### 1. Enable Middleware

```python
# main.py
from fastapi import FastAPI
from swx_core.middleware import TenantContextMiddleware

app = FastAPI()
app.add_middleware(TenantContextMiddleware)
```

### 2. Add tenant_id to Models

```python
# swx_app/models/product.py
from swx_core.models.base import Base

class Product(Base, table=True):
    __tablename__ = "product"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    tenant_id: UUID = Field(index=True, foreign_key="swx_team.id")
```

### 3. Use TenantAwareRepository

```python
# swx_app/repositories/product_repository.py
from swx_core.repositories import TenantAwareRepository
from swx_app.models.product import Product

class ProductRepository(TenantAwareRepository[Product]):
    def __init__(self):
        super().__init__(model=Product, tenant_field="tenant_id")
```

### 4. Use TenantAwareController

```python
# swx_app/controllers/product_controller.py
from swx_core.controllers import TenantAwareController
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic

class ProductController(TenantAwareController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
        )
```

---

## Tenant Context API

### Setting Context

```python
from swx_core.core.tenant import set_current_tenant, set_current_team, set_super_admin

# Set tenant context
set_current_tenant(organization_id)

# Set team context (for team-scoped operations)
set_current_team(team_id)

# Enable super-admin mode (bypasses tenant filtering)
set_super_admin(True)
```

### Getting Context

```python
from swx_core.core.tenant import get_current_tenant_id, get_current_team_id, is_super_admin

tenant_id = get_current_tenant_id()
team_id = get_current_team_id()
is_admin = is_super_admin()
```

### Context Managers

```python
from swx_core.core.tenant import tenant_context, super_admin_context

# Temporary tenant switch
with tenant_context(new_tenant_id):
    # Queries run in different tenant context
    products = await repository.find_all()

# Temporary super-admin mode
with super_admin_context():
    # Access all tenants
    all_products = await repository.find_all()
```

---

## TenantAwareRepository

### Features

- Automatic tenant filtering on all read operations
- **Fail-closed tenant isolation** — when no tenant context is set, queries return no rows instead of all rows (v2.7.22)
- Auto-injection of tenant_id on create operations
- Super-admin bypass support
- Team-scoped filtering

### Methods

| Method | Behavior |
|--------|----------|
| `find_by_id(id)` | Returns record only if in current tenant |
| `find_all()` | Returns all records in current tenant |
| `find_by(**filters)` | Filters by tenant + additional criteria |
| `create(data)` | Auto-injects tenant_id if not present |
| `update(id, data)` | Validates record in tenant before update |
| `delete(id)` | Validates record in tenant before delete |
| `count(**filters)` | Counts only records in current tenant |

### Team-Scoped Filtering

```python
# Filter by team instead of tenant
repository = TenantAwareRepository(model=Task, team_field="team_id")
```

### Platform-Level and Team-Scoped Records

`LLMProviderConfig`, `Notification`, and `ApiKey` support an optional `team_id`.

- `team_id IS NULL` - platform-level record visible to all teams
- `team_id IS NOT NULL` - team-scoped record visible only within that team context

Use the repository or service methods that accept `team_id` to include the correct scope:

```python
api_keys = await list_api_keys(session, team_id=team_id)
provider_configs = await repository.get_all(session, team_id=team_id)
notifications = await repository.get_all(session, team_id=team_id)
```

When you want automatic filtering instead of passing `team_id` manually, use `TenantAwareRepository`
with `team_field="team_id"` so the current team context is applied automatically.

---

## TenantContextMiddleware

### Default Behavior

1. Extracts tenant from request headers or authenticated user
2. Sets context variables for request duration
3. Cleans up context in finally block

### Tenant Resolution Order

1. `X-Tenant-ID` header
2. `X-Team-ID` header
3. `user.tenant_id` from authenticated user
4. `user.current_team_id` from authenticated user
5. `user.is_superuser` enables bypass mode

### Exempt Paths

Default exempt paths (no tenant context required):

- `/api/access/auth` - Login endpoints
- `/api/access/oauth` - OAuth endpoints
- `/api/utils/health` - Health checks
- `/docs` - API documentation
- `/openapi.json` - OpenAPI schema

---

## EntitlementService

### Quota Enforcement

```python
from swx_core.services.billing.quota_service import EntitlementService
from swx_core.models.billing import BillingAccountType

service = EntitlementService(session)

# Check quota
remaining = await service.require_quota(
    owner_id=user_id,
    account_type=BillingAccountType.USER,
    feature_key="api.calls",
    quantity=1
)

# Check boolean feature
has_access = await service.require_feature(
    owner_id=team_id,
    account_type=BillingAccountType.TEAM,
    feature_key="advanced_analytics"
)
```

### FastAPI Dependencies

```python
from swx_core.services.billing.quota_service import require_quota_dependency

@router.post("/items", dependencies=[Depends(require_quota_dependency("items.create"))])
async def create_item(data: ItemCreate, session: SessionDep):
    # If we get here, quota check passed
    return await service.create(data)
```

### Error Handling

```python
from swx_core.services.billing.quota_service import QuotaExceededError

try:
    await service.require_quota(owner_id, account_type, "api.calls", 10)
except QuotaExceededError as e:
    print(f"Feature: {e.feature}, Limit: {e.limit}, Used: {e.current}")
```

---

## PostgreSQL Row-Level Security

### Enable RLS

```sql
-- Enable RLS on table
ALTER TABLE swx_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE swx_users FORCE ROW LEVEL SECURITY;

-- Create tenant isolation policy
CREATE POLICY users_tenant_isolation ON swx_users
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Super-admin bypass policy
CREATE POLICY users_super_admin_bypass ON swx_users
    FOR ALL
    USING (current_setting('app.is_super_admin', true)::boolean = true);
```

### SQLAlchemy Integration

```python
from swx_core.database.rls import setup_rls_event_listeners

# Called automatically on connection
# Sets PostgreSQL session variables from context
```

---

## Best Practices

### DO

- ✅ Add `tenant_id` to all tenant-scoped models
- ✅ Use TenantAwareRepository for automatic filtering
- ✅ Index `tenant_id` columns
- ✅ Use composite indexes with `tenant_id` as leading column

### DON'T

- ❌ Bypass tenant filtering in production code
- ❌ Forget to clear context in middleware
- ❌ Use global variables for tenant context (use contextvars)
- ❌ Skip RLS for security-critical applications

---

## Migration Guide

### From Manual Filtering

**Before:**
```python
async def get_products(session: AsyncSession, tenant_id: UUID):
    stmt = select(Product).where(Product.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return result.scalars().all()
```

**After:**
```python
async def get_products():
    # Tenant filtering is automatic
    return await repository.find_all()
```

### Adding to Existing Models

```sql
-- Add tenant_id column
ALTER TABLE products ADD COLUMN tenant_id UUID;
CREATE INDEX ix_products_tenant_id ON products(tenant_id);
ALTER TABLE products ADD CONSTRAINT fk_products_tenant 
    FOREIGN KEY (tenant_id) REFERENCES swx_team(id);
```

---

## Testing Multi-Tenant Code

```python
from swx_core.core.tenant import tenant_context
from uuid import uuid4

async def test_tenant_isolation():
    tenant_a = uuid4()
    tenant_b = uuid4()
    
    # Create product in tenant A
    with tenant_context(tenant_a):
        product_a = await repository.create({"name": "Product A"})
    
    # Create product in tenant B
    with tenant_context(tenant_b):
        product_b = await repository.create({"name": "Product B"})
    
    # Verify isolation
    with tenant_context(tenant_a):
        products = await repository.find_all()
        assert len(products) == 1
        assert products[0].name == "Product A"
```
