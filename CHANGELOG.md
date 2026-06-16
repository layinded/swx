# Changelog

All notable changes to this project will be documented in this file.

## [2.7.20] - 2026-06-16

### Fixed - CRITICAL
- **`bootstrap_app()` crash on FastAPI 0.115.0+** - Fixed `AttributeError: '_IncludedRouter'
  object has no attribute 'path'` on line 123 of `bootstrap.py`. FastAPI 0.115.0+ wraps
  included sub-routers in `_IncludedRouter` objects that lack a `.path` attribute. Added
  the same `hasattr(r, "path")` guard that line 119 already had, safely skipping wrapper
  objects. Without this fix, the server crashes on every startup when using
  `include_router()` with FastAPI >= 0.115.0.

## [2.7.19] - 2026-05-29

### Fixed
- **Post-registration hook exception handling** - Hook failures no longer mask successful
  user creation with a 400 error. Post-hook exceptions are now caught and logged as
  warnings, and the `user.created` event is always emitted regardless of hook outcome.
  Previously, a failing post-hook would prevent the event from firing and return a 400
  error even though the user was successfully created.

## [2.7.18] - 2026-05-29

### Fixed - CRITICAL
- **Core routes not mounted** - Fixed `dynamic_import` returning package `__init__.py` modules
  alongside individual route files, causing double registration and 404 errors.
  Package modules in route directories are now skipped; only leaf route files are registered.
- **Auth route prefix doubling** - Fixed `/api/auth/auth/` double prefix caused by `__init__.py`
  aggregation routers being processed alongside individual route files.
- **Misleading "No core routes found" warning** - Fixed `for...else` bug in `router.py` that
  printed "No core routes found" even when routes were successfully loaded.

### Added
- **Registration Hook Registry** - `swx_core.core.hooks.registration_hooks` singleton for
  configuring pre/post registration hooks at app startup. The auth route endpoint now
  automatically uses registered hooks, solving the "hooks not exposed via HTTP API" issue.
- **Explicit tenant_id in TenantAwareRepository** - New `explicit_tenant_id` and `explicit_team_id`
  constructor parameters allow bypassing context vars for apps that pass tenant explicitly:
  ```python
  repo = TenantAwareRepository(Product, explicit_tenant_id="tenant-123")
  ```

### Changed
- **TenantAwareRepository** - `_apply_tenant_filter` now respects explicit tenant/team IDs over
  context vars. Super-admin bypass only applies when no explicit ID is set.
- **Auth controller** - `register_controller` now passes `registration_hooks.pre_register` and
  `registration_hooks.post_register` to `register_user_service`.

## [2.7.17] - 2026-05-29

### Added - Registration Extension Points
- **Lifecycle Hooks for Registration** - `register_user_service()` now accepts hook parameters:
  - `pre_register_hook` - Async function called BEFORE user creation for validation/tenant assignment
  - `post_register_hook` - Async function called AFTER user creation for organization setup/side effects
  - Hook execution order: pre → create → post → emit event → return user
  - Both hooks receive `event_context` for passing custom data
- **CORE_ROUTE_PREFIX Setting** - Configurable prefix for core framework routes:
  - Default: `""` (empty string) - core routes at `/api/auth`
  - Set to `"/v1"` for `/api/v1/auth` to match versioned app routes
  - Enables apps to mount core routes consistently with their API versioning

### New Documentation
- **Registration Hooks** - `docs/04-core-concepts/REGISTRATION_HOOKS.md`
  - Complete guide to registration extension points
  - Examples: multi-tenant registration, invitation-based signup, enterprise SSO
  - Comparison of hooks vs events vs service override approaches
- **Route Configuration** - `docs/02-getting-started/ROUTE_CONFIGURATION.md`
  - Route prefix configuration explained
  - Migration guide for swx_app compatibility
  - Troubleshooting common routing issues

### Changed
- **Router** - Core routes respect `CORE_ROUTE_PREFIX` setting for URL mounting
- **Settings** - Added `CORE_ROUTE_PREFIX` field with default empty string
- **GETTING_STARTED.md** - Added `CORE_ROUTE_PREFIX` to environment variables documentation

## [2.7.16] - 2026-05-29

### Added - Multi-Tenant Support
- **TenantAwareRepository** - Base repository with automatic tenant filtering via context variables
  - Automatically filters queries by `tenant_id` or `team_id` from request context
  - Supports super-admin bypass for accessing all tenants
  - Auto-injects tenant context on create operations
- **TenantContextMiddleware** - Middleware for extracting and setting tenant context
  - Extracts tenant from `X-Tenant-ID` header or authenticated user
  - Implements context cleanup in finally block to prevent leakage
  - Exempts auth and health endpoints
- **TenantAwareController** - Base controller with tenant context injection
  - Extends BaseController with automatic tenant data injection
  - Works with TenantAwareRepository for full tenant isolation
- **EntitlementService** - Service for quota enforcement and feature entitlements
  - `require_quota()` - Check if owner has remaining quota
  - `require_feature()` - Check access to boolean features
  - `QuotaExceededError` exception with feature/limit/current details
  - Dependency helpers: `require_quota_dependency()`, `require_feature_dependency()`
- **PostgreSQL RLS Support** - Row-Level Security integration
  - `swx_core/database/rls.py` - SQLAlchemy event listeners for RLS
  - `swx_core/database/migrations/rls_template.sql` - Migration template for enabling RLS

### Changed
- **User Model** - Added `tenant_id` field to `UserBase` for multi-tenant support
- **Auth Dependencies** - `get_current_user()` now sets tenant context for downstream use
- **Repositories** - Added `TenantAwareRepository` export to `__init__.py`
- **Controllers** - Added `TenantAwareController` export to `__init__.py`
- **Middleware** - Added `TenantContextMiddleware` export to `__init__.py`

### New Modules
- `swx_core/core/tenant.py` - ContextVar-based tenant context management
- `swx_core/core/__init__.py` - Core module exports
- `swx_core/repositories/tenant_aware.py` - TenantAwareRepository implementation
- `swx_core/controllers/tenant_aware.py` - TenantAwareController implementation
- `swx_core/middleware/tenant_middleware.py` - TenantContextMiddleware implementation
- `swx_core/services/billing/quota_service.py` - EntitlementService implementation

## [2.7.15] - 2026-05-29

### Fixed - CRITICAL
- **Routes Not Mounted** - Fixed routes not accessible despite being logged as registered
  - Root cause: `__init__.py` files in routes subdirectories only imported routers but didn't create module-level `router` variable
  - Fix: Added `router = APIRouter()` + `router.include_router()` aggregations in each `__init__.py`
  - Affected files: `swx_core/routes/access/__init__.py`, `swx_core/routes/admin/__init__.py`, `swx_core/routes/user/__init__.py`, `swx_core/routes/utils/__init__.py`
  - Impact: All routes from swx_core/routes/* now properly accessible

### Fixed
- **Router Prefix Handling** - Fixed v2.7.14 bug where router prefixes were incorrectly stripped
- **User Model Timestamps** - Added `created_at` and `updated_at` fields to User model
- **Timezone-Aware DateTime** - Fixed `datetime.now(timezone.utc)` causing PostgreSQL errors for TIMESTAMP WITHOUT TIME ZONE columns
  - Changed to `datetime.utcnow()` for naive datetime compatibility

### Documentation
- **Router Module Pattern** - Documented requirement for module-level `router` variable in route `__init__.py` files

## [2.7.8] - 2026-05-01

### Fixed - CRITICAL
- **Job Runner SQL Bug** - Fixed unqualified column reference `job.status` → `swx_job.status` in PostgreSQL query
  - Error: `missing FROM-clause entry for table "job"` in PostgreSQL
  - File: `swx_core/services/job/job_runner.py:202`
  - Fix: Changed `text("job.status = ANY(...)")` → `text("swx_job.status = ANY(...)")`
  - Impact: Background job processing was completely broken, workers spammed errors

### Fixed
- **get_current_user Export** - Added `get_current_user` and `UserDep` to `swx_core.auth.__init__.py`
  - Users can now: `from swx_core.auth import get_current_user`
  - Previously required workaround: `from swx_core.auth.user import get_current_user`

### Documentation
- **AdminUser Import Path** - Confirmed correct path: `from swx_core.models import AdminUser`
  - No `swx_core.models.admin` module exists - AdminUser is in `admin_user.py`

## [2.7.7] - 2026-05-01

### Fixed - CRITICAL
- **SyntaxError in ai_exports/graph.py** - Removed corrupt prefixes (#MY|, #NS|, etc.) causing unterminated string literal
- **SyntaxError in ai_exports/contracts.py** - Same corruption fix
- **swx CLI now works** - Fixed blocking import error

### Changed
- Removed autogenerate from `swx setup` to prevent issues with existing projects
- `swx setup` now provides manual instructions instead of auto-generating migrations
- Safer for projects with custom tables that reference core tables

### Bug Fixes
- ai_exports files no longer have corrupt line prefixes
- Existing projects with migrations can safely run `swx setup`

## [2.7.6] - 2026-05-01

### Fixed - Database Migration Auto-Generation
- **swx_job Table Not Created** - Setup command now auto-generates initial migration if none exist
  - `swx setup` detects empty migrations/versions/ directory
  - Automatically runs `alembic revision --autogenerate -m "initial"`
  - Creates all framework tables including `swx_job`, `swx_users`, `swx_role`, etc.
  
### Changed
- `_setup_database()` in `framework.py` now generates initial migration on fresh projects
- Users no longer need to manually run `swx db revision "initial"` first

## [2.7.5] - 2026-05-01

### Fixed - Import/Module Issues
- **Broken Import in CLI Framework** - Fixed `swx_core/cli/commands/framework.py:239` importing from non-existent `swx_core.database.core`. Changed to `swx_core.database.db`.
- **Database Module Exports** - Added exports to `swx_core/database/__init__.py` for cleaner imports:
  - `AsyncSessionLocal`, `SessionLocal` - session factories
  - `async_engine`, `engine` - database engines
  - `get_async_db`, `get_db`, `get_session` - dependency injectors
  - `SessionDep`, `SyncSessionDep` - type annotations

### Documentation
- Confirmed cache functions are correctly located at `swx_core.utils.cache` (not `swx_core.cache`)
- Confirmed BaseRepository is at `swx_core.repositories.base` (not `swx_core.repository`)

## [2.7.4] - 2026-04-29

### Fixed - CRITICAL
- **All Services: Local EventBus Instance Bug** - Fixed ALL services creating local `EventBus()` instances instead of using the global `event_bus` singleton. This affected:
  - `role_service.py` (5 occurrences)
  - `user_service.py` (3 occurrences)
  - `permission_service.py` (3 occurrences)
  - `team_service.py` (5 occurrences)
  - `user_role_service.py` (2 occurrences)
  - `policy_service.py` (3 occurrences)
  - `base.py` (BaseService class)
  
  **Impact**: ALL events emitted by these services were going to empty buses with NO registered listeners. Fix ensures all events go to the global singleton where listeners are registered.

### Changed
- All services now import and use `event_bus` singleton from `swx_core.events.dispatcher`
- BaseService now stores reference to global `event_bus` instead of creating new instance

## [2.7.3] - 2026-04-29

### Fixed - CRITICAL
- **user.created Event Not Emitted** - Fixed `register_user_service()` creating a local `EventBus()` instance instead of using the global `event_bus` singleton. Events are now emitted to the correct bus where listeners are registered.
- **Event Context Empty Dict Handling** - Changed `if event_context:` to `if event_context is not None:` to correctly handle empty dict.

### Added
- **Discovery Diagnostic Logging** - Added DEBUG-level logs explaining why Phase 3 listener registration might be skipped
- **diagnose_discovery() Function** - New helper to debug discovery configuration:
  ```python
  from swx_core.bootstrap import diagnose_discovery
  diagnose_discovery()  # Returns app_exists, has_listeners, phase_3_will_run
  ```

### Changed
- **Bootstrap Phase 3** - Now logs DEBUG message when skipping listener registration, showing which directory is missing

## [2.7.2] - 2026-04-29

### Added
- **Event Dispatch Logging** - INFO-level logging for event dispatch with listener count, execution times, and completion status
- **Listener Registration Logging** - INFO-level logging when listeners are registered with pattern, priority, and queueable details
- **Event Debug Utilities** - New `swx_core.events.debug` module with inspection tools:
  - `list_all_listeners()` - List all registered listeners grouped by event
  - `test_pattern()` - Test wildcard pattern matching
  - `trace_event()` - Trace which listeners receive an event
  - `print_event_bus_status()` - Print comprehensive event bus status
  - `get_listener_count()` - Count registered listeners
  - `verify_listener_registered()` - Verify a listener is registered
- **Example Listeners** - Template project includes example listener implementations in `swx_app/listeners/example_listeners.py`

### Changed
- **Listener registration logging** - Changed from DEBUG to INFO level for visibility
- **Event dispatch logging** - Added detailed timing and listener invocation logging

### Fixed
- **Listener visibility** - Listeners now log at INFO level when registered during bootstrap

### Documentation
- **Event System Guide** - Added troubleshooting section to `docs/04-core-concepts/EVENT_SYSTEM.md`
- **Debug utilities documentation** - Documented all debug utilities with examples
- **Pattern matching examples** - Added wildcard pattern examples and tests

## [2.7.1] - 2026-04-29

### Fixed
- **Critical: Event Hashability** - Fixed `unhashable type: 'Event'` bug by adding `__hash__` method to Event class
- **Critical: TypedEvent Hashability** - Added `__hash__` method to TypedEvent class for use in sets/dicts
- **Wildcard Pattern Matching** - Fixed bug where `user.*` pattern matched all events instead of only `user.created`, `user.deleted`, etc.
- **Event Context Handling** - Fixed empty dict `event_context={}` being treated as `None` (now correctly adds `"context": {}` to payload)

### Added
- **TypedEvent `__hash__` method** - TypedEvent objects can now be used in sets and as dict keys
- **ListenerRegistration.pattern field** - Stores pattern for wildcard listeners (supports `*`, `user.*`, `*.created`)
- **EventBus._matches_pattern()** - Pattern matching logic for wildcard event listeners
- **Comprehensive edge case tests** - 25 new tests for event emission edge cases

### Changed
- **Event context parameter** - Changed from `if event_context else` to `if event_context is not None else` across all services to correctly handle empty dict

## [2.7.0] - 2026-04-28

### Added
- **Comprehensive Event Emission**: All SwX services now emit domain events for CRUD operations
- **Event Context Parameter**: All service methods accept `event_context` parameter for additional metadata
- **Typed Event Base Classes**: New `TypedEvent` base class for type-safe event handling

### Services with Event Emission

#### Authentication & User Management
- **auth_service.py**: `register_user_service()` now emits `user.created` event
- **user_service.py**: 
  - `update_user_profile_service()` emits `user.updated` event
  - `update_password_service()` emits `user.password_changed` event
  - `delete_user_service()` emits `user.deleted` event

#### Role & Permission Management
- **role_service.py**:
  - `create_role_service()` emits `role.created` event
  - `update_role_service()` emits `role.updated` event
  - `delete_role_service()` emits `role.deleted` event
  - `assign_permission_to_role_service()` emits `role.permission_assigned` event
  - `remove_permission_from_role_service()` emits `role.permission_removed` event

- **permission_service.py**:
  - `create_permission_service()` emits `permission.created` event
  - `update_permission_service()` emits `permission.updated` event
  - `delete_permission_service()` emits `permission.deleted` event

#### Team Management
- **team_service.py**:
  - `create_team_service()` emits `team.created` event
  - `update_team_service()` emits `team.updated` event
  - `delete_team_service()` emits `team.deleted` event
  - `add_team_member_service()` emits `team.member_added` event
  - `remove_team_member_service()` emits `team.member_removed` event

#### User-Role Management
- **user_role_service.py**:
  - `assign_role_to_user_service()` emits `user_role.assigned` event
  - `remove_role_from_user_service()` emits `user_role.removed` event

#### Policy Management
- **policy_service.py**:
  - `create_policy_service()` emits `policy.created` event
  - `update_policy_service()` emits `policy.updated` event
  - `delete_policy_service()` emits `policy.deleted` event

### Event Payload Structure

All events follow a consistent payload structure:

```python
# Create/Update/Delete events
{
    "id": "uuid-string",
    "data": {"field": "value"},           # Resource data
    "context": {"key": "value"}            # Optional context
}

# Update events (additional fields)
{
    "id": "uuid-string",
    "old_values": {"field": "old_value"},
    "new_values": {"field": "new_value"},
    "context": {"key": "value"}            # Optional context
}
```

### Example Usage

```python
# User registration with context
user = await register_controller(
    session=session,
    user_in=user_create,
    request=request,
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# Role creation with context
role = await create_role_service(
    session=session,
    role_in=role_create,
    event_context={"created_by": admin_id},
)
```

### Tests
- **New Tests**: `tests/services/test_service_event_emissions.py` with comprehensive event tests
- **New Tests**: `tests/services/test_user_created_event.py` for user registration events
- **Coverage**: 23 tests covering all service event emissions

### Breaking Changes
- None - all changes are backward compatible

### Migration Guide
No migration required. Event emission is automatic. To receive additional context:

1. Pass `event_context` parameter to any service method:
   ```python
   await create_role_service(session, role_in, event_context={"created_by": user_id})
   ```

2. Listen for events using EventBus:
   ```python
   from swx_core.events import EventBus
   
   @EventBus.on("role.created")
   async def on_role_created(event):
       role_id = event.payload["id"]
       context = event.payload.get("context", {})
       created_by = context.get("created_by")
   ```

## [2.6.0] - 2026-04-28

### Added
- **Event Context Enhancement**: BaseService CRUD methods now accept `event_context` parameter for additional context in event payloads
- **before_emit Hook**: Async hook called before event emission to enhance payload with computed/async context
- **after_emit Hook**: Async hook called after event emission for side effects
- **Structured Event Payloads**: Events now support `{"id": ..., "data": ..., "context": ...}` structure

### Changed
- **BaseService.create()**: Added `event_context: Dict[str, Any] | None` parameter
- **BaseService.update()**: Added `event_context` parameter
- **BaseService.delete()**: Added `event_context` parameter
- **BaseService.soft_delete()**: Added `event_context` parameter
- **BaseService.restore()**: Added `event_context` parameter
- **BaseService.bulk_create()**: Added `event_context` parameter

### Example Usage
```python
# Before: Workaround with duplicate events
user = await user_service.create(data)
await event_bus.dispatch("user.created", payload={...context...})

# After: Single event with context
user = await user_service.create(
    data={"email": "user@example.com", "password": "secret"},
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# With before_emit hook for computed context
class UserService(BaseService[User]):
    async def before_emit(self, event_name, payload, instance):
        if event_name == "user.created" and instance:
            payload["context"] = {
                **payload.get("context", {}),
                "user_type": await self._determine_user_type(instance),
            }
        return payload
```

### Industrial Standard Compliance
- Follows Django Signals pattern (`sender + **kwargs`)
- Follows Flask/Blinker pattern (explicit context injection)
- Follows SQLAlchemy event hooks (before/after pattern)
- Follows production SaaS patterns (aden-hive/hive, ricequant/rqalpha)

### Tests
- **New Tests**: `tests/services/test_base_service_event_context.py` with 10 comprehensive tests
- **Coverage**: event_context propagation, before_emit/after_emit hooks, backward compatibility

## [2.5.0] - 2025-04-28

### Added
- **Event Listener Auto-Discovery**: Listeners in `swx_core/events/listeners/` and `swx_app/listeners/` are automatically discovered and registered during bootstrap
- **Listener Auto-Registration**: No manual EventServiceProvider registration needed - listeners self-register
- **Wildcard Pattern Support**: Listeners can use wildcard patterns like `user.*`, `emergency.*`, or `*` for all events
- **Priority-Based Execution**: Listeners execute in priority order (highest first)
- **Queueable Listeners**: Support for background queue processing with `queueable=True`
- **New Functions in `swx_core.events`**:
  - `discover_listeners(module)`: Find all Listener subclasses in a module
  - `register_listener(listener_class)`: Register a listener with EventBus
  - `load_listeners_from_path(base_path, package_name)`: Load listeners from directory
  - `load_all_listeners()`: Load and register all core and app listeners
- **New Module**: `swx_core/events/listener_loader.py` with auto-discovery implementation
- **New Directory**: `swx_core/events/listeners/` for core framework listeners
- **New Tests**: `tests/events/test_listener_loader.py` with comprehensive coverage
- **New Documentation**: `docs/04-core-concepts/EVENT_SYSTEM.md` with examples and best practices

### Fixed
- **Bootstrap Integration**: `register_event_listeners()` now properly called during bootstrap (Phase 3)
- **Import Exports**: All listener_loader functions now properly exported in `swx_core/events/__init__.py`
- **Path Handling**: Fixed `path_exists` issue in listener_loader using `Path.exists()` directly

### Changed
- **EventListener Pattern**: Now follows Laravel's EventServiceProvider pattern for auto-discovery
- **Bootstrap Phases**: Added Phase 3 for listener registration after provider boot

## [2.4.0] - 2025-04-27

### Added
- **Table Prefix**: All framework tables now use `swx_` prefix to differentiate core tables from user tables
- **Migration Support**: Migration script to rename existing tables with `swx_` prefix
- **Foreign Key Updates**: All 16 foreign key references updated to use prefixed table names

### Changed
- **Table Names**: 21 core tables renamed with `swx_` prefix
- **Raw SQL**: Updated 5 raw SQL queries to use prefixed table names

## [2.3.16] - 2025-04-27

### Fixed
- **Circular Import**: Fixed circular import in `loader.py` when SwX loader tries to reload modules
- **Module Loading**: Added `_loading_modules` tracking to prevent recursive loading

## [2.0.0] - 2024-03-XX

### Added
- **Base Classes Pattern**: BaseController, BaseService, BaseRepository for rapid development
- **Domain Separation**: Admin, User, and System domains completely isolated
- **OAuth2 + JWT**: Secure token-based authentication with refresh tokens
- **Permission-First RBAC**: Fine-grained access control with team scoping
- **Policy Engine (ABAC)**: Attribute-based access control with conditions
- **Billing & Entitlements**: Feature registry, plan management, Stripe integration
- **Rate Limiting**: Plan-based rate limits with burst protection
- **Audit Logging**: Immutable security and business event logs
- **Background Jobs**: Asynchronous job processing with retries
- **CLI Tools**: `swx` command for scaffolding with `--base` flag
