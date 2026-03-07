# Acceptance Testing

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Acceptance Criteria](#acceptance-criteria)
3. [Full User Simulation](#full-user-simulation)
4. [Endpoint Coverage](#endpoint-coverage)
5. [State Validation](#state-validation)
6. [Running Acceptance Tests](#running-acceptance-tests)
7. [Interpreting Results](#interpreting-results)

---

## Overview

SwX-API includes **comprehensive acceptance testing** via the full user simulation script. This serves as the **final acceptance gate** before production deployment.

### Acceptance Test Goals

- ✅ **100% Endpoint Coverage** - All API endpoints tested
- ✅ **Complete Persona Flows** - All user types tested
- ✅ **State Integrity** - Database integrity verified
- ✅ **No Unexpected Errors** - Fails on unexpected errors
- ✅ **Readable Logs** - Clear test output

---

## Acceptance Criteria

### Must Pass

**1. System Seeding**
- Permissions seeded successfully
- Roles seeded successfully
- Plans and features seeded successfully
- Settings seeded successfully

**2. Authentication**
- Admin login works
- User login works
- Token refresh works
- Logout works

**3. Authorization**
- Permission checks work
- Policy evaluation works
- Domain separation enforced

**4. CRUD Operations**
- Create operations work
- Read operations work
- Update operations work
- Delete operations work

**5. State Integrity**
- No orphan records
- Foreign key integrity maintained
- Audit logs complete
- Billing consistency verified

---

## Full User Simulation

### Simulation Script

**Location:** `scripts/full_user_simulation.py`

**What It Tests:**
- System Operator flow
- Admin User flow
- Team Owner flow
- Team Member flow
- All API endpoints
- State integrity

### Running Acceptance Tests

**From Host:**
```bash
# Set environment variables
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme
export RUN_PHASE0=1  # Hard reset

# Run acceptance test
python scripts/full_user_simulation.py
```

**From Container:**
```bash
# Run inside container
docker compose exec swx-api bash -c "
  export API_URL=http://localhost:8000/api
  export RUN_PHASE0=0
  python scripts/full_user_simulation.py
"
```

### Expected Output

**Success:**
```
[sim] Phase 0: Hard reset + compose up
[sim] Phase 1: System seeding
[sim] Phase 2: Persona flows
[sim] Phase 3: State validation
[sim] === ACCEPTANCE TEST PASSED ===
```

**Failure:**
```
[sim] FAIL: GET /api/admin/user/ -> 500 (expected 200) body=...
```

---

## Endpoint Coverage

### Coverage Report

**Location:** `docs/ENDPOINT_COVERAGE.md`

**What It Documents:**
- All API endpoints
- Which persona tests each endpoint
- Expected responses
- Coverage status

### Coverage Verification

**Automatic:**
- Simulation script tests all endpoints
- Coverage tracked in documentation
- Missing endpoints identified

**Manual:**
```bash
# Check OpenAPI schema
curl http://localhost:8001/openapi.json | jq '.paths | keys'
```

---

## State Validation

### Validation Checks

**1. Foreign Key Integrity**
- No orphaned records
- All foreign keys valid
- Referential integrity maintained

**2. Audit Log Completeness**
- All security events logged
- All business events logged
- No missing audit logs

**3. Billing Consistency**
- Subscriptions linked to plans
- Entitlements linked to features
- Usage records linked to accounts

**4. Data Integrity**
- No duplicate records
- Unique constraints enforced
- Required fields present

### Running Validation

**Standalone:**
```bash
python scripts/validate_state.py
```

**After Simulation:**
```bash
# Included in simulation
python scripts/full_user_simulation.py
```

---

## Running Acceptance Tests

### Pre-Test Setup

**1. Clean State:**
```bash
# Hard reset
./scripts/hard_reset.sh

# Or via simulation
export RUN_PHASE0=1
```

**2. Start Services:**
```bash
docker compose up -d
```

**3. Wait for Health:**
```bash
# Wait for services to be healthy
sleep 60
```

### Running Tests

**Basic:**
```bash
python scripts/full_user_simulation.py
```

**With Environment:**
```bash
export API_URL=http://localhost:8001/api
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=changeme
export RUN_PHASE0=1

python scripts/full_user_simulation.py
```

### Test Output

**Success Indicators:**
- All phases complete
- No unexpected errors
- State validation passes
- "ACCEPTANCE TEST PASSED" message

**Failure Indicators:**
- Unexpected HTTP status codes
- Missing data
- State validation failures
- "FAIL:" messages

---

## Interpreting Results

### Success Criteria

**All Must Pass:**
- ✅ System seeding completes
- ✅ All persona flows complete
- ✅ All endpoints return expected status codes
- ✅ State validation passes
- ✅ No unexpected errors

### Failure Analysis

**Common Failures:**
1. **Rate Limit Errors** - Increase limits or add delays
2. **Authentication Errors** - Check credentials
3. **Permission Errors** - Verify permissions seeded
4. **Database Errors** - Check migrations applied
5. **State Validation Errors** - Review data integrity

### Debugging Failures

**Check Logs:**
```bash
# Application logs
docker compose logs swx-api

# Simulation output
python scripts/full_user_simulation.py 2>&1 | tee simulation.log
```

**Check State:**
```bash
# Validate state
python scripts/validate_state.py

# Check database
docker compose exec db psql -U postgres -d swx_api
```

---

## Next Steps

- Read [Testing Guide](./TESTING_GUIDE.md) for testing patterns
- Read [Seeding & Simulation](./SEEDING_AND_SIMULATION.md) for simulation tools
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production operations

---

**Status:** Acceptance testing guide documented, ready for implementation.
