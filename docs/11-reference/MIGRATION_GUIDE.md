# Migration Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Database Migrations](#database-migrations)
3. [Application Updates](#application-updates)
4. [Configuration Changes](#configuration-changes)
5. [Breaking Changes](#breaking-changes)
6. [Rollback Procedures](#rollback-procedures)

---

## Overview

This guide covers **migration procedures** for upgrading SwX-API between versions. Follow these procedures to ensure smooth upgrades.

### Migration Types

1. **Database Migrations** - Schema changes
2. **Application Updates** - Code changes
3. **Configuration Changes** - Environment variable changes
4. **Breaking Changes** - Incompatible changes

---

## Database Migrations

### Running Migrations

**Upgrade:**
```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific revision
alembic upgrade <revision>
```

**Downgrade:**
```bash
# Rollback one revision
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision>
```

**Check Status:**
```bash
# Current revision
alembic current

# Migration history
alembic history

# Check for conflicts
alembic check
```

### Migration Best Practices

**Before Migration:**
1. Backup database
2. Review migration script
3. Test in staging
4. Plan rollback

**During Migration:**
1. Run during maintenance window
2. Monitor migration progress
3. Check for errors
4. Verify data integrity

**After Migration:**
1. Verify schema changes
2. Test application
3. Monitor for issues
4. Keep backup until verified

---

## Application Updates

### Update Process

**Step 1: Backup**
```bash
# Backup database
docker compose exec db pg_dump -U ${DB_USER} ${DB_NAME} > backup-$(date +%Y%m%d).sql

# Backup code
git tag backup-$(date +%Y%m%d)
```

**Step 2: Pull Updates**
```bash
# Pull latest code
git pull origin main

# Check for breaking changes
git log --oneline HEAD..origin/main
```

**Step 3: Update Dependencies**
```bash
# Update dependencies
uv sync

# Or
pip install -r requirements.txt
```

**Step 4: Run Migrations**
```bash
# Apply migrations
alembic upgrade head
```

**Step 5: Restart Services**
```bash
# Restart application
docker compose restart swx-api

# Or rebuild
docker compose up -d --build
```

**Step 6: Verify**
```bash
# Check health
curl http://localhost:8001/api/utils/health-check

# Run tests
python scripts/full_user_simulation.py
```

---

## Configuration Changes

### Environment Variables

**New Variables:**
```bash
# Add to .env
NEW_VARIABLE=value
```

**Changed Variables:**
```bash
# Update in .env
OLD_VARIABLE=new_value
```

**Removed Variables:**
```bash
# Remove from .env
# OLD_VARIABLE=value  # Commented out or removed
```

### Settings Migration

**Runtime Settings:**
```bash
# Settings are in database
# Update via API or seed script
python scripts/seed_settings.py
```

---

## Breaking Changes

### Version Compatibility

**Check Changelog:**
- Review breaking changes
- Check migration requirements
- Verify compatibility

### Breaking Change Examples

**1. Model Changes:**
- Field removed
- Field type changed
- Required field added

**2. API Changes:**
- Endpoint removed
- Request/response format changed
- Authentication requirements changed

**3. Configuration Changes:**
- Environment variable removed
- Required variable added
- Default value changed

---

## Rollback Procedures

### Application Rollback

**Step 1: Stop Current Version**
```bash
docker compose down
```

**Step 2: Checkout Previous Version**
```bash
git checkout <previous-tag>
```

**Step 3: Rebuild and Start**
```bash
docker compose up -d --build
```

**Step 4: Verify**
```bash
curl http://localhost:8001/api/utils/health-check
```

### Database Rollback

**Step 1: Backup Current State**
```bash
docker compose exec db pg_dump -U ${DB_USER} ${DB_NAME} > backup-before-rollback.sql
```

**Step 2: Rollback Migration**
```bash
docker compose exec swx-api alembic downgrade -1
```

**Step 3: Verify**
```bash
docker compose exec swx-api alembic current
```

### Full Rollback

**Step 1: Restore Database**
```bash
docker compose exec -T db psql -U ${DB_USER} ${DB_NAME} < backup.sql
```

**Step 2: Restore Code**
```bash
git checkout <previous-tag>
```

**Step 3: Rebuild and Start**
```bash
docker compose up -d --build
```

---

## Next Steps

- Read [Changelog](./CHANGELOG.md) for version history
- Read [Operations Guide](../08-operations/OPERATIONS.md) for operations
- Read [Deployment Guide](../08-operations/DEPLOYMENT.md) for deployment

---

**Status:** Migration guide documented, ready for implementation.
