# Changelog

**Version:** 2.1.0  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Overview](#overview)
2. [Version History](#version-history)
3. [Breaking Changes](#breaking-changes)
4. [Deprecations](#deprecations)

---

## Overview

This document tracks **version history and changes** for SwX-API. All notable changes are documented here.

### Version Format

**Semantic Versioning:** `MAJOR.MINOR.PATCH`

- **MAJOR** - Breaking changes
- **MINOR** - New features, backward compatible
- **PATCH** - Bug fixes, backward compatible

---

## Version History

### Version 2.1.0 (2026-03-07)

**Framework Improvements**

**New Utilities:**
- ✅ Unit of Work pattern (`UnitOfWork`, `UnitOfWorkManager`, `@transactional` decorator) - Transaction management with automatic commit/rollback
MS|- ✅ Filter Builder (`FilterBuilder`, `SortBuilder`, `FilterParams`) - Fluent query filtering and sorting
TJ|- ✅ Database resilience (`pool_pre_ping`, `pool_recycle` settings) - Connection health checks and recycling
- ✅ API Versioning helpers (`VersionedRouter`, `deprecated_version`, `negotiate_version`) - Version management and deprecation
**Middleware Improvements:**
- ✅ Fixed CORS middleware auto-loading (`apply_middleware` hook)
- ✅ Fixed Sentry middleware auto-loading (`apply_middleware` hook)
- ✅ Fixed Metrics middleware auto-loading (`apply_middleware` hook)
- ✅ Updated middleware `__init__.py` exports for clean imports

**CLI Improvements:**
- ✅ Added `BASE_TEMPLATES` for modern BaseController/BaseService/BaseRepository patterns
- ✅ Added `--base` flag to `swx make:resource` command for modern scaffolding
- ✅ Scaffolding now supports both legacy (`swx make:resource Product`) and modern patterns (`swx make:resource Product --base`)

**Documentation:**
- ✅ Added USAGE_EXAMPLES.md with complete code examples for all base classes
- ✅ Added MIGRATION_GUIDE.md for v1.x to v2.0 migration
- ✅ Updated README.md with v2.0 base classes section

**Technical Details:**
- `swx_core/utils/unit_of_work.py` - UnitOfWork, UnitOfWorkManager, @transactional decorator
- `swx_core/utils/filters.py` - FilterBuilder, SortBuilder, FilterParams, FilterOperator
- `swx_core/database/db.py` - Added pool_pre_ping=True, pool_recycle=3600
- `swx_core/middleware/__init__.py` - Fixed exports, added apply_middleware functions
RQ|- `swx_core/cli/commands/resource_templates.py` - Added BASE_TEMPLATES dictionary
NQ|- `swx_core/cli/commands/make.py` - Added --base flag
- `swx_core/utils/versioning.py` - VersionedRouter, deprecated_version, negotiate_version, list_versions
- `tests/cli/test_make_commands.py` - CLI scaffolding tests

---

### Version 2.0.0 (2026-01-26)

**Base Classes Release**

**New Features:**
- ✅ BaseController - Full CRUD endpoints in minutes with hooks and events
- ✅ BaseService - Business logic with validation hooks and DTOs
- ✅ BaseRepository - Data access with pagination, filtering, soft-delete
- ✅ Comprehensive documentation (BASE_CLASSES.md, UTILITIES.md)

**Core Features (from v1.0.0):**
- ✅ Authentication (Admin, User, System domains)
- ✅ RBAC (Permission-first, team-scoped)
- ✅ Policy Engine (ABAC)
- ✅ Billing & Entitlements
- ✅ Rate Limiting
- ✅ Audit Logging
- ✅ Alerting System
- ✅ Background Jobs
- ✅ Runtime Settings
- ✅ Async Model
- ✅ Comprehensive Documentation

**Security:**
- ✅ Domain separation
- ✅ Token security
- ✅ Secrets management
- ✅ Security best practices

**Operations:**
- ✅ Docker deployment
- ✅ Health checks
- ✅ Monitoring
- ✅ Backup & recovery

**Testing:**
- ✅ Unit tests
- ✅ Integration tests
- ✅ Acceptance tests
- ✅ Simulation tools

---

### Version 1.0.0 (2026-01-15)

**Initial Release**

**Features:**
- ✅ Authentication (Admin, User, System domains)
- ✅ RBAC (Permission-first, team-scoped)
- ✅ Policy Engine (ABAC)
- ✅ Billing & Entitlements
- ✅ Rate Limiting
- ✅ Audit Logging
- ✅ Alerting System
- ✅ Background Jobs
- ✅ Runtime Settings
- ✅ Async Model
- ✅ Comprehensive Documentation

**Security:**
- ✅ Domain separation
- ✅ Token security
- ✅ Secrets management
- ✅ Security best practices

**Operations:**
- ✅ Docker deployment
- ✅ Health checks
- ✅ Monitoring
- ✅ Backup & recovery

**Testing:**
- ✅ Unit tests
- ✅ Integration tests
- ✅ Acceptance tests
- ✅ Simulation tools

---

## Breaking Changes

### Version 2.0.0

**Recommended Changes (Non-Breaking):**
- Replace static CRUD functions with BaseController/BaseService/BaseRepository pattern
- Update CLI commands to use `--base` flag for modern scaffolding

### Version 1.0.0

**No breaking changes** - Initial release.

---

## Deprecations

### Version 2.1.0

**Deprecated:**
- Static CRUD scaffolding (use `--base` flag for modern patterns)

### Version 1.0.0

**No deprecations** - Initial release.

---

## Migration Notes

### Version 2.0.0

**Upgrading from v1.x:**
- Read [Migration Guide](../07-extending/MIGRATION_GUIDE.md) for step-by-step instructions
- No breaking changes - existing code continues to work
- Optionally migrate to BaseController/BaseService/BaseRepository pattern

### Version 1.0.0

**Initial Setup:**
- Run migrations: `alembic upgrade head`
- Seed system: `python scripts/seed_system.py`
- Configure environment: Set required `.env` variables

---

## Next Steps

- Read [Migration Guide](../07-extending/MIGRATION_GUIDE.md) for v1.x to v2.0 migration
- Read [Base Classes](../04-core-concepts/BASE_CLASSES.md) for BaseController/BaseService/BaseRepository usage
- Read [Utilities](../04-core-concepts/UTILITIES.md) for all utility modules
- Read [Usage Examples](../04-core-concepts/USAGE_EXAMPLES.md) for complete code examples
- Read [Overview](../01-overview/OVERVIEW.md) for framework introduction

---

**Status:** Changelog updated for v2.1.0 release.