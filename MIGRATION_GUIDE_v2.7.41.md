# Migration Guide: v2.7.40 → v2.7.41

## Critical Bugs Fixed

This release fixes two critical bugs discovered in v2.7.40:

### BUG-1: InvitationStatus StrEnum Case Mismatch

**Problem:** `InvitationStatus` used lowercase values (`"pending"`, `"accepted"`, etc.) but PostgreSQL ENUM columns are case-sensitive. When asyncpg binds the parameter, it uses the enum's `.name` attribute which is UPPERCASE (`PENDING`, `ACCEPTED`), causing PostgreSQL to reject values.

**Symptoms:**
- All `TeamInvitationService` queries filtering by `InvitationStatus.PENDING` fail with HTTP 500
- Error: `invalid input value for enum invitationstatus: "PENDING"`

**Fix:** Changed `InvitationStatus` enum values to uppercase to match PostgreSQL ENUM expectations:
```python
# BEFORE (v2.7.40)
class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    # ...

# AFTER (v2.7.41)
class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    # ...
```

**Action Required:** If you created PostgreSQL enums with lowercase values, you need to recreate them:
```sql
-- Drop the old enum (if no data exists)
DROP TYPE IF EXISTS invitationstatus CASCADE;

-- The enum will be recreated automatically with uppercase values
-- Or manually:
CREATE TYPE invitationstatus AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'REVOKED');
```

### BUG-2: swx_team_member.role_id NOT NULL Constraint

**Problem:** The v2.7.40 model removed `role_id` from `TeamMember` (replaced by `team_role_id`), but the database column still exists as `NOT NULL` with no default value. When creating team members, only `team_role_id` is provided, leaving `role_id` as NULL - which violates the constraint.

**Symptoms:**
- POST `/admin/team/member` fails with HTTP 500
- Error: `null value in column "role_id" of relation "swx_team_member" violates not-null constraint`

**Fix:** The database column needs to be made nullable or dropped entirely.

**Migration Required:**
```bash
# Create migration
alembic revision -m "make_team_member_role_id_nullable"

# Edit the migration file:
```

```python
"""make_team_member_role_id_nullable

Revision ID: YOUR_REVISION_ID
Revises: PREVIOUS_REVISION_ID
Create Date: 2024-01-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'YOUR_REVISION_ID'
down_revision = 'PREVIOUS_REVISION_ID'  # Replace with your current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make role_id nullable (legacy column from RBAC migration)
    op.alter_column(
        'swx_team_member',
        'role_id',
        existing_type=sa.UUID(),
        nullable=True
    )


def downgrade() -> None:
    # Revert role_id to NOT NULL
    # WARNING: This will fail if NULL values exist
    op.alter_column(
        'swx_team_member',
        'role_id',
        existing_type=sa.UUID(),
        nullable=False
    )
```

**Alternative: Drop the column entirely if no longer used:**
```python
def upgrade() -> None:
    # Drop legacy role_id column (replaced by team_role_id)
    op.drop_column('swx_team_member', 'role_id')


def downgrade() -> None:
    # Recreate role_id column (if needed)
    op.add_column(
        'swx_team_member',
        sa.Column('role_id', sa.UUID(), sa.ForeignKey('swx_roles.id'), nullable=True)
    )
```

## Verification Steps

After upgrading to v2.7.41:

### 1. Verify InvitationStatus Fix

```bash
# Test invitation creation
curl -X POST http://localhost:8001/api/admin/team/invite \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "TEAM_UUID",
    "invitee_email": "test@example.com",
    "team_role_id": "ROLE_UUID"
  }'

# Should return 200 OK with invitation details
# Should NOT return 500 error
```

### 2. Verify Team Member Creation

```bash
# Test team member creation
curl -X POST http://localhost:8001/api/admin/team/member \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "TEAM_UUID",
    "user_id": "USER_UUID",
    "team_role_id": "ROLE_UUID"
  }'

# Should return 200 OK with member details
# Should NOT return 500 error about role_id constraint
```

### 3. Run Migration Status Check

```bash
# Check migration status
alembic current

# Should show your latest migration applied
```

## Complete Upgrade Steps

```bash
# 1. Upgrade package
pip install swx-core==2.7.41

# 2. Create and run migration
alembic revision -m "make_team_member_role_id_nullable"
# Edit migration file (see above)
alembic upgrade head

# 3. Restart application
docker compose restart backend-api

# 4. Verify fixes (see Verification Steps above)
```

## Breaking Changes

**None** - These are pure bug fixes with no breaking changes to the API.

## Database Changes

- **InvitationStatus enum:** Values changed from lowercase to uppercase (PENDING, ACCEPTED, etc.)
- **swx_team_member.role_id:** Needs migration to make nullable or drop column

## Rollback

If you need to rollback to v2.7.40:

```bash
# 1. Downgrade package
pip install swx-core==2.7.40

# 2. Revert database migration
alembic downgrade -1

# 3. Recreate PostgreSQL enum with lowercase values (if needed)
DROP TYPE IF EXISTS invitationstatus CASCADE;
CREATE TYPE invitationstatus AS ENUM ('pending', 'accepted', 'rejected', 'expired', 'revoked');
```

## Questions?

If you encounter issues during migration:

1. Check logs: `docker compose logs backend-api`
2. Verify migration status: `alembic current`
3. Check database constraints: `\d swx_team_member` in psql
4. Contact support with error details and migration logs