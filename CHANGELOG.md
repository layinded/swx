# Changelog

All notable changes to this project will be documented in this file.

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
