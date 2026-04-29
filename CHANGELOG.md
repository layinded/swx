# Changelog

All notable changes to this project will be documented in this file.

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
