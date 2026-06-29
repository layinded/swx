# Multi-Tenant Migration Guide

This guide explains how to migrate existing applications to use swx-core's multi-tenant features introduced in v2.7.16.

---

## Overview

The multi-tenant support adds a `tenant_id` field to the User model, enabling automatic data isolation between tenants/organizations.

---

## Migration Paths

### Option 1: New Application (Recommended)

For new projects, multi-tenant support is automatic:

1. **Install swx-core 2.7.16+**
   ```bash
   pip install swx-core>=2.7.16
   ```

2. **Add tenant_id to your models**
   ```python
   from swx_core.models.base import Base
   
   class Product(Base, table=True):
       name: str
       tenant_id: UUID = Field(index=True, foreign_key="swx_team.id")
   ```

3. **Enable TenantContextMiddleware**
   ```python
   from swx_core.middleware import TenantContextMiddleware
   app.add_middleware(TenantContextMiddleware)
   ```

4. **Use TenantAwareRepository**
   ```python
   from swx_core.repositories import TenantAwareRepository
   
   class ProductRepository(TenantAwareRepository[Product]):
       def __init__(self):
           super().__init__(model=Product)
   ```

---

### Option 2: Existing Single-Tenant Application

**Scenario**: You have existing users and data, now migrating to multi-tenant.

#### Step 1: Run Migration

```bash
# Copy migration template to your project
cp swx_core/database/migrations/add_tenant_id_migration.py your_project/migrations/versions/

# Edit down_revision to point to your current head
# Then run:
alembic upgrade head
```

#### Step 2: Create Default Tenant

```sql
-- Create a default tenant for existing users
INSERT INTO swx_team (id, name, description, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Organization',
    'Default tenant for legacy users',
    NOW(),
    NOW()
);
```

#### Step 3: Assign Existing Users

```sql
-- Assign all existing users to default tenant
UPDATE swx_users 
SET tenant_id = '00000000-0000-0000-0000-000000000001'
WHERE tenant_id IS NULL;
```

#### Step 4: Make Column NOT NULL (Optional)

```sql
-- If all users must belong to a tenant
ALTER TABLE swx_users ALTER COLUMN tenant_id SET NOT NULL;
```

#### Step 5: Update Registration Flow

```python
# swx_app/routes/auth_route.py
from swx_core.core.tenant import get_current_tenant_id

@router.post("/register")
async def register(user_in: UserCreate, session: SessionDep):
    # Get tenant from context (set by middleware)
    tenant_id = get_current_tenant_id()
    
    # Or create new tenant for each registration
    if not tenant_id:
        team = await create_team_service(
            session,
            TeamCreate(name=f"{user_in.email}'s Organization")
        )
        tenant_id = team.id
    
    # User will be auto-assigned tenant_id via TenantAwareRepository
    user = await register_user_service(session, user_in)
    return user
```

---

### Option 3: Existing Multi-Tenant Application

**Scenario**: You already have multi-tenant logic but with different field names (e.g., `org_id`, `company_id`).

#### Option A: Rename Field in Database

```sql
-- Add tenant_id as alias for your existing field
ALTER TABLE swx_users ADD COLUMN tenant_id UUID;

-- Copy values from your existing field
UPDATE swx_users SET tenant_id = org_id;

-- Create index
CREATE INDEX ix_swx_users_tenant_id ON swx_users(tenant_id);
```

#### Option B: Configure Custom Field Name

```python
# In your repository
from swx_core.repositories import TenantAwareRepository

class ProductRepository(TenantAwareRepository[Product]):
    def __init__(self):
        # Use your existing field name
        super().__init__(model=Product, tenant_field="org_id")
```

```python
# In your controller
from swx_core.controllers import TenantAwareController

class ProductController(TenantAwareController[Product, ...]):
    def __init__(self):
        super().__init__(
            model=Product,
            tenant_field="org_id",
            ...
        )
```

---

## Setting Tenant Context

### From JWT Token

Update your authentication to include tenant_id in token claims:

```python
# swx_core/auth/core/jwt.py
def create_token(subject: str, audience: TokenAudience, ...):
    to_encode = {
        "sub": subject,
        "aud": audience.value,
        "tenant_id": str(tenant_id),  # Add tenant to token
    }
```

Then update the dependency:

```python
# swx_core/auth/user/dependencies.py
async def get_current_user(...):
    # ... existing code ...
    
    # Extract tenant from token
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        set_current_tenant(UUID(tenant_id))
    
    return user
```

### From Request Header

The default `TenantContextMiddleware` already supports `X-Tenant-ID` header:

```bash
curl -H "X-Tenant-ID: <tenant-uuid>" https://api.example.com/products
```

### From User's Organization

If users belong to an organization:

```python
# swx_core/auth/user/dependencies.py
async def get_current_user(session: SessionDep, token: str) -> User:
    user = await get_user_from_token(token, session)
    
    # Set tenant from user's organization
    if user.organization_id:
        set_current_tenant(user.organization_id)
    
    return user
```

---

## Testing the Migration

### Verify Column Added

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'swx_users' AND column_name = 'tenant_id';
```

Expected:
```
column_name | data_type | is_nullable
------------+-----------+------------
tenant_id   | uuid      | YES
```

### Verify Index Created

```sql
SELECT indexname FROM pg_indexes
WHERE tablename = 'swx_users' AND indexname = 'ix_swx_users_tenant_id';
```

### Test Tenant Isolation

```python
from swx_core.core.tenant import tenant_context
from uuid import uuid4

async def test_tenant_isolation():
    tenant_a = uuid4()
    tenant_b = uuid4()
    
    # Create product in tenant A
    with tenant_context(tenant_a):
        p1 = await repository.create({"name": "Product A"})
    
    # Create product in tenant B
    with tenant_context(tenant_b):
        p2 = await repository.create({"name": "Product B"})
    
    # Verify isolation
    with tenant_context(tenant_a):
        products = await repository.find_all()
        assert len(products) == 1
        assert products[0].name == "Product A"
    
    # Verify super-admin sees all
    with super_admin_context():
        all_products = await repository.find_all()
        assert len(all_products) == 2
```

---

## Rollback Plan

If migration causes issues:

```bash
# Rollback migration
alembic downgrade -1

# Or specific revision
alembic downgrade add_tenant_id_to_users
```

This will:
1. Drop the index `ix_swx_users_tenant_id`
2. Remove the `tenant_id` column

**Warning**: Rollback will lose tenant assignments. Backup before migrating.

---

## Common Issues

### Issue: "tenant_id is required" error

**Cause**: Your code expects tenant_id but new users don't have it.

**Solution**:
1. Make `tenant_id` nullable in model
2. Or auto-assign default tenant in registration
3. Or make it required with default value

### Issue: "Cannot filter by tenant_id - column doesn't exist"

**Cause**: Migration not applied.

**Solution**: Run `alembic upgrade head`

### Issue: Existing users have NULL tenant_id

**Cause**: Migration added column but didn't backfill.

**Solution**:
```sql
UPDATE swx_users SET tenant_id = '<default-tenant-uuid>' WHERE tenant_id IS NULL;
```

### Issue: Super-admin can't see all tenants

**Cause**: Super-admin context not set.

**Solution**:
```python
from swx_core.core.tenant import set_super_admin

# In auth dependency
if user.is_superuser:
    set_super_admin(True)
```

---

## Checklist

- [ ] Run migration: `alembic upgrade head`
- [ ] Create default tenant (if needed)
- [ ] Backfill existing users (if needed)
- [ ] Update registration flow to set tenant_id
- [ ] Add TenantContextMiddleware
- [ ] Update repositories to TenantAwareRepository
- [ ] Test tenant isolation
- [ ] Test super-admin bypass
- [ ] Update API documentation