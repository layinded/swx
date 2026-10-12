# Migration Guide: v2.7.38 for FastPII Integration

**Release Date:** 2026-07-05
**Critical Fixes:** Schema gaps, API field names, model exports

---

## Executive Summary

This release fixes 3 critical issues blocking FastPII integration:
1. **API Field Bug**: `role_id` → `team_role_id` in team member endpoints
2. **Missing Migration**: `swx_team_member.created_at` and `updated_at` columns
3. **Model Exports**: All models now properly exported in `__init__.py`

---

## Critical Issues Fixed

### CRITICAL-1: swx_team Missing Columns (v2.7.22 Migration)

**Status:** ✅ Migration already exists

The v2_7_22_schema_changes.py migration adds:
- `swx_team.owner_id` (UUID, nullable, FK → swx_users.id)
- `swx_team.created_at` (timestamp, default now())
- `swx_team.updated_at` (timestamp, default now())
- FK cascade updates on swx_user_role, swx_team_member, swx_users, etc.

**Action Required:**
```bash
# 1. Copy migration to your project
cp swx_core/database/migrations/v2_7_22_schema_changes.py \
   your_project/migrations/versions/

# 2. Update down_revision to your current head
# Edit the file and set: down_revision = "your_current_head"

# 3. Run migration
alembic upgrade head
```

### CRITICAL-2: swx_team_member Missing Columns (NEW v2.7.38 Migration)

**Status:** ✅ NEW migration created

The v2_7_38_team_member_timestamps.py migration adds:
- `swx_team_member.created_at` (timestamp, default now())
- `swx_team_member.updated_at` (timestamp, default now())

**Note:** The UniqueConstraint(team_id, user_id) was already added in v2_7_24_add_team_member_unique.py

**Action Required:**
```bash
# 1. Copy migration to your project
cp swx_core/database/migrations/v2_7_38_team_member_timestamps.py \
   your_project/migrations/versions/

# 2. Update down_revision to your current head
# Edit the file and set: down_revision = "v2_7_24_team_member_unique"

# 3. Run migration
alembic upgrade head
```

### CRITICAL-3: API Field Name Bug (Fixed in Code)

**Status:** ✅ Fixed in v2.7.38

**Before:**
```python
# team_route.py line 225
return [TeamMemberPublic(id=m.id, team_id=m.team_id, user_id=m.user_id, role_id=m.role_id) for m in members]

# team_controller.py line 27
return TeamMemberPublic(id=member.id, team_id=member.team_id, user_id=member.user_id, role_id=member.role_id)
```

**After:**
```python
# team_route.py line 225
return [TeamMemberPublic(
    id=m.id,
    team_id=m.team_id,
    user_id=m.user_id,
    team_role_id=m.team_role_id,
    created_at=m.created_at,
) for m in members]

# team_controller.py line 27
return TeamMemberPublic(
    id=member.id,
    team_id=member.team_id,
    user_id=member.user_id,
    team_role_id=member.team_role_id,
    created_at=member.created_at,
)
```

**Impact:** API now returns correct field name `team_role_id` instead of legacy `role_id`

---

## Migration Chain

**Required Order:**

```
v2_7_22_schema_changes.py          # Team.owner_id, created_at, updated_at + FK cascades
    ↓
v2_7_24_team_member_unique.py      # TeamMember UniqueConstraint(team_id, user_id)
    ↓
v2_7_38_team_member_timestamps.py # TeamMember.created_at, updated_at
```

**Full Migration Commands:**
```bash
# Step 1: Apply v2.7.22 schema changes
alembic upgrade v2_7_22_schema_changes

# Step 2: Apply v2.7.24 unique constraint
alembic upgrade v2_7_24_team_member_unique

# Step 3: Apply v2.7.38 team member timestamps
alembic upgrade v2_7_38_team_member_timestamps

# Or upgrade to head directly (if down_revision is set correctly)
alembic upgrade head
```

---

## Database Schema After Migration

### swx_team Table
| Column | Type | Constraints | Status |
|--------|------|-------------|--------|
| id | UUID | PRIMARY KEY | ✅ Existing |
| name | VARCHAR(255) | NOT NULL | ✅ Existing |
| description | VARCHAR(500) | | ✅ Existing |
| tenant_id | UUID | | ✅ Existing |
| owner_id | UUID | FK → swx_users.id (SET NULL) | ✅ NEW (v2.7.22) |
| created_at | TIMESTAMP | DEFAULT NOW() | ✅ NEW (v2.7.22) |
| updated_at | TIMESTAMP | DEFAULT NOW() | ✅ NEW (v2.7.22) |

### swx_team_member Table
| Column/Constraint | Type | Constraints | Status |
|-------------------|------|-------------|--------|
| id | UUID | PRIMARY KEY | ✅ Existing |
| team_id | UUID | FK → swx_team.id (CASCADE) | ✅ Existing (v2.7.22 updated cascade) |
| user_id | UUID | FK → swx_users.id (CASCADE) | ✅ Existing (v2.7.22 updated cascade) |
| team_role_id | UUID | FK → swx_team_role.id (CASCADE) | ✅ Existing |
| created_at | TIMESTAMP | DEFAULT NOW() | ✅ NEW (v2.7.38) |
| updated_at | TIMESTAMP | DEFAULT NOW() | ✅ NEW (v2.7.38) |
| uq_team_member_user_team | UNIQUE(team_id, user_id) | | ✅ NEW (v2.7.24) |

---

## Legacy Column Note

**role_id Column:**
- The `swx_team_member.role_id` column exists in the database (legacy FK → swx_role.id)
- It's NOT in the model (TeamMember uses `team_role_id` instead)
- **Do NOT drop it yet** — it's still referenced by admin routes
- Future migration: Deprecate and remove `role_id` after all routes migrate to `team_role_id`

---

## Model Exports (MEDIUM-1)

**Status:** ✅ Already fixed in v2.7.37

All models are now properly exported in `swx_core/models/__init__.py`:
- TeamRole, TeamRoleCreate, TeamRoleUpdate, TeamRolePublic, DEFAULT_TEAM_ROLES
- TeamInvitation, TeamInvitationCreate, TeamInvitationPublic, InvitationStatus
- TeamMemberUpdate

**Usage:**
```python
# Now works correctly
from swx_core.models import TeamRole, TeamInvitation, TeamMemberUpdate
```

---

## Installation

```bash
# Upgrade to v2.7.38
pip install --upgrade swx-core==2.7.38

# Or with uv
uv pip install swx-core==2.7.38
```

---

## Verification Steps

After applying migrations, verify:

```sql
-- Check swx_team has new columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'swx_team'
  AND column_name IN ('owner_id', 'created_at', 'updated_at');

-- Check swx_team_member has new columns and constraint
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'swx_team_member'
  AND column_name IN ('created_at', 'updated_at');

SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'swx_team_member'
  AND constraint_name = 'uq_team_member_user_team';
```

---

## Rollback Plan

If issues arise:

```bash
# Downgrade to previous version
alembic downgrade v2_7_24_team_member_unique

# Or fully revert
alembic downgrade v2_7_22_schema_changes
```

---

## Breaking Changes

**API Response Field Change:**
- `TeamMemberPublic.role_id` → `TeamMemberPublic.team_role_id`
- Clients must update to use `team_role_id` field
- Old field `role_id` no longer returned

**Database Schema:**
- New non-nullable columns with default values (safe migration)
- No data loss or transformation required
- Existing rows will get `NOW()` as default timestamps

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/swx-team/swx-core/issues
- Documentation: docs/05-security/SECURITY_BEST_PRACTICES.md

---

**Author:** Abdulbasit Aliyu (layinded@gmail.com)
**Version:** v2.7.38
**Date:** 2026-07-05