# Seeding & Simulation

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [System Seeding](#system-seeding)
3. [User Simulation](#user-simulation)
4. [Personas](#personas)
5. [Running Simulations](#running-simulations)
6. [State Validation](#state-validation)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API includes **comprehensive seeding and simulation tools** for testing and development. These tools create realistic test data and simulate complete user workflows.

### Key Features

- ✅ **Idempotent Seeding** - Safe to run multiple times
- ✅ **Complete Personas** - Predefined user roles and permissions
- ✅ **End-to-End Simulation** - Full user workflows
- ✅ **State Validation** - Post-simulation integrity checks
- ✅ **Production Acceptance** - Final acceptance gate

---

## System Seeding

### Seed Script

**Location:** `scripts/seed_system.py`

**What It Seeds:**
- Permissions (RBAC permissions)
- Roles (Admin, Editor, Viewer, etc.)
- Billing Plans (Free, Pro, Team, Enterprise)
- Billing Features (API requests, storage, etc.)
- Plan Entitlements (Plan-feature mappings)
- Runtime Settings (Token expiration, rate limits, etc.)

### Running Seed Script

**From Host:**
```bash
# Set environment variables
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme

# Run seed script
python scripts/seed_system.py
```

**From Container:**
```bash
# Run inside container
docker compose exec swx-api python scripts/seed_system.py
```

### Idempotency

**Safe to Run Multiple Times:**
- Checks if data exists before creating
- Updates existing data if needed
- No duplicate records

**Example:**
```python
# Check if permission exists
existing = await get_permission_by_name(session, permission_name)
if existing:
    # Update if needed
    ...
else:
    # Create new
    ...
```

---

## User Simulation

### Full User Simulation

**Location:** `scripts/full_user_simulation.py`

**What It Does:**
- Hard reset (optional, Phase 0)
- System seeding
- Persona creation
- End-to-end workflow simulation
- State validation

### Running Simulation

**From Host:**
```bash
# Set environment variables
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme
export RUN_PHASE0=1  # Hard reset + compose up

# Run simulation
python scripts/full_user_simulation.py
```

**From Container:**
```bash
# Run inside container (stack already up)
export RUN_PHASE0=0
docker compose exec swx-api python scripts/full_user_simulation.py
```

### Simulation Phases

**Phase 0: Clean State (Optional)**
- Hard reset (docker compose down -v)
- Compose up
- Wait for services to be healthy

**Phase 1: System Seeding**
- Seed permissions, roles, plans, features
- Seed runtime settings
- Create admin user

**Phase 2: Persona Flows**
- System Operator flow
- Admin User flow
- Team Owner flow
- Team Member flow

**Phase 3: State Validation**
- Foreign key integrity
- Orphan record checks
- Audit log completeness
- Billing consistency

---

## Personas

### System Operator

**Purpose:** System administration

**Credentials:**
- Email: `admin@example.com`
- Password: From `ADMIN_PASSWORD` env var

**Permissions:**
- All admin permissions
- System configuration
- User management
- Audit log access

**Workflow:**
- Login
- Create permissions
- Create roles
- Create users
- Create teams
- Manage billing
- View audit logs

### Admin User

**Purpose:** Administrative operations

**Credentials:**
- Created during simulation
- Unique email per run

**Permissions:**
- Admin permissions
- User management
- Team management

**Workflow:**
- Login
- Manage users
- Manage teams
- Manage roles
- Manage permissions

### Team Owner

**Purpose:** Team management

**Credentials:**
- Created during simulation
- Unique email per run

**Permissions:**
- Team-scoped permissions
- Team management
- Team member management

**Workflow:**
- Register
- Create team
- Add team members
- Manage team resources
- Update team settings

### Team Member

**Purpose:** Regular user operations

**Credentials:**
- Created during simulation
- Unique email per run

**Permissions:**
- Limited permissions
- Team member permissions

**Workflow:**
- Register
- Join team
- Access team resources
- Update profile

---

## Running Simulations

### Basic Simulation

**Minimal Setup:**
```bash
# Set required variables
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme

# Run simulation
python scripts/full_user_simulation.py
```

### Full Simulation with Reset

**Complete Reset:**
```bash
# Set variables
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme
export RUN_PHASE0=1  # Enable Phase 0 (hard reset)

# Run simulation
python scripts/full_user_simulation.py
```

### Container-Based Simulation

**Inside Container:**
```bash
# Start services
docker compose up -d

# Run simulation inside container
docker compose exec swx-api bash -c "
  export API_URL=http://localhost:8000/api
  export RUN_PHASE0=0
  python scripts/full_user_simulation.py
"
```

---

## State Validation

### Validation Script

**Location:** `scripts/validate_state.py`

**What It Validates:**
- Foreign key integrity
- Orphan records
- Audit log completeness
- Billing consistency
- Data integrity

### Running Validation

**Standalone:**
```bash
python scripts/validate_state.py
```

**After Simulation:**
```bash
# Simulation includes validation
python scripts/full_user_simulation.py
```

### Validation Checks

**Foreign Key Integrity:**
```sql
-- Check for orphaned records
SELECT * FROM user_role ur
LEFT JOIN user u ON ur.user_id = u.id
WHERE u.id IS NULL;
```

**Audit Log Completeness:**
```sql
-- Check for missing audit logs
SELECT action, COUNT(*) 
FROM audit_log
GROUP BY action;
```

**Billing Consistency:**
```sql
-- Check subscription-plan consistency
SELECT s.id, s.plan_id, p.id as plan_exists
FROM subscription s
LEFT JOIN plan p ON s.plan_id = p.id
WHERE p.id IS NULL;
```

---

## Best Practices

### ✅ DO

1. **Run from clean state for acceptance tests**
   ```bash
   # ✅ Good - Clean state
   export RUN_PHASE0=1
   python scripts/full_user_simulation.py
   ```

2. **Validate state after simulation**
   ```bash
   # ✅ Good - Validate state
   python scripts/validate_state.py
   ```

3. **Use unique emails per run**
   ```python
   # ✅ Good - Unique emails
   email = f"user_{timestamp}@example.com"
   ```

4. **Handle expected errors gracefully**
   ```python
   # ✅ Good - Handle expected errors
   try:
       result = req(client, "GET", "/api/admin/user/", token=token)
   except Exception as e:
       if "No users found" in str(e):
           warn("Expected: No users in clean state")
       else:
           raise
   ```

### ❌ DON'T

1. **Don't skip validation**
   ```bash
   # ❌ Bad - No validation
   python scripts/full_user_simulation.py
   # No validation run
   
   # ✅ Good - Validate
   python scripts/full_user_simulation.py
   python scripts/validate_state.py
   ```

2. **Don't use hardcoded credentials**
   ```python
   # ❌ Bad - Hardcoded
   email = "user@example.com"
   
   # ✅ Good - Environment variable
   email = os.getenv("ADMIN_EMAIL", "admin@example.com")
   ```

---

## Next Steps

- Read [Testing Guide](./TESTING_GUIDE.md) for testing patterns
- Read [Acceptance Testing](./ACCEPTANCE_TESTING.md) for acceptance test procedures
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production operations

---

**Status:** Seeding & simulation guide documented, ready for implementation.
