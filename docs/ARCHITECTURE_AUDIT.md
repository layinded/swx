# SWX Core Architecture Audit & Improvement Plan

**Date**: 2025-09-05
**Auditor**: Sisyphus (OhMyOpenCode)
**Scope**: Make SWX Core a reusable production application framework so applications (QiroPrint, NeuronaHealth, AFCloud) have thin, declarative `main.py` files instead of manually implementing framework behavior.

---

## 1. Current SWX Architecture Map

### 1.1 Two Conflicting Initialization Paths

SWX has **two independent, unsynchronized initialization paths** that can both run for the same application:

**Path A — `main.py` standalone** (`swx_core/main.py`):
- Module-level `load_all_modules()` — imports all models/services/repositories/middleware at import time
- `lifespan()` async context manager — 12+ sequential startup steps
- Direct `FastAPI()` instantiation with exception handlers
- `load_middleware(app)` — dynamic middleware discovery
- `app.include_router(router)` — auto-discovered routes
- Shutdown: cancel background tasks, stop Redis bridge, stop audit queue

**Path B — `bootstrap_app()`** (`swx_core/bootstrap.py`):
- Creates/retrieves global Container singleton
- Loads core providers (6 providers sorted by priority)
- Discovers user providers from `swx_app/providers/`
- Phase 1: `register()` all providers
- Phase 2: `boot()` all providers
- Phase 2.5: Register default hooks
- Phase 3: Discover user event listeners
- Returns Container

**Critical problem**: These two paths do NOT compose. If an app uses `bootstrap_app()` AND `main.py`'s `lifespan()`, providers get registered twice and services start twice. If only `bootstrap_app()` is used, the lifespan steps (DB migration, job runner, audit queue, etc.) must be manually replicated.

### 1.2 Container / Dependency Injection

**File**: `swx_core/container/container.py`

- Laravel-style IoC container with string-keyed bindings
- Binding types: `bind()` (transient), `singleton()`, `scoped()`, `instance()`
- Contextual binding: `when().needs().give()`
- Circular dependency detection via `_build_stack` tracking
- Thread-safe singleton resolution (double-checked locking)
- Scoped resolution for per-request instances
- Tags, aliases, extenders, resolving/resolved callbacks
- Global singleton pattern: `_container` module variable

**FastAPI integration** (`swx_core/container/fastapi_integration.py`):
- `inject(abstract)` — FastAPI `Depends` that resolves from container
- `inject_class(cls)` — resolves by class name
- `scoped_inject(abstract)` — per-request scoped
- `ContainerMiddleware` — wraps each request in `container.async_scope()`
- `setup_container()` — alternative to `bootstrap_app()` using `ProviderRegistry`

### 1.3 Provider System

**File**: `swx_core/providers/base.py`

6 core providers (sorted by priority):

| Priority | Provider | Key Services |
|----------|----------|-------------|
| 10 | DatabaseServiceProvider | `db.engine`, `db.session_factory`, `db.session` |
| 15 | EventServiceProvider | `events`/`EventBus`/`event_bus` |
| 20 | AuthServiceProvider | `auth.*` guards, token blacklist |
| 30 | RateLimitServiceProvider | `redis.client`, `rate_limiter`, `abuse_detector` |
| 35 | EventBridgeServiceProvider | `event_bridge` (conditional on Redis) |
| 40 | BillingServiceProvider | `billing.*` services |

`ServiceProvider` base class:
- `priority: int = 100` — ordering
- `defer: bool = False` — declared but NOT implemented (deferred loading)
- `depends: List[str] = []` — declared but NOT enforced
- Two-phase lifecycle: `register()` (bind only) → `boot()` (resolve OK)
- Helper methods: `bind()`, `singleton()`, `scoped()`, `instance()`, `when_needs()`, `alias()`, `tag()`, `extend()`

**Override mechanism**: App providers (priority 1000+) can re-bind services using `singleton()`/`instance()`. There is also `container.extend()` for decorator-style modification.

### 1.4 Middleware Stack

13+ middleware modules, each with `apply_middleware(app)`:

| Middleware | Type | Key Function |
|-----------|------|-------------|
| SessionMiddleware | Starlette | Cookie-based sessions |
| CORSMiddleware | Starlette | CORS from settings |
| LoggingMiddleware | Pure ASGI | Structured request logging (SOC 2 CC7.2) |
| RateLimitMiddleware | Pure ASGI | Per-user/IP rate limiting |
| AuditMiddleware | Pure ASGI | Request ID assignment |
| SecurityHeadersMiddleware | Pure ASGI | CSP, HSTS, X-Frame-Options |
| TenantContextMiddleware | Pure ASGI | Tenant context extraction |
| CSRFMiddleware | Pure ASGI | Double-submit cookie CSRF |
| AuthRateLimitMiddleware | Pure ASGI | Path-aware auth rate limiting |
| RateLimitHeadersMiddleware | Pure ASGI | X-RateLimit-* response headers |
| SentryMiddleware | SDK hook | Sentry error tracking |
| MetricsMiddleware | Pure ASGI | Prometheus metrics |
| RegionRoutingMiddleware | Pure ASGI | Geographic region routing |
| ContainerMiddleware | ASGI | Per-request container scope |

**Ordering problem**: Middleware is applied in filesystem discovery order (alphabetical by module name). FastAPI middleware is LIFO (last added = outermost), so the effective execution order depends on which `apply_middleware()` functions run last. This is **not deterministic** and is a security concern (e.g., CORS must be outer, audit must be inner).

### 1.5 Exception Handling

4 exception handlers registered in `main.py`:

1. `StarletteHTTPException` → `{"error": exc.detail}`
2. `RequestValidationError` → Structured 422 with safe body serialization
3. `SwXError` → `{"success": false, "error": {"code", "message", "details"}}`
4. `Exception` → `{"error": "Internal Server Error", "request_id": ...}`

**SwXError hierarchy** (`swx_core/utils/errors.py`):
- Base `SwXError` with `code`, `message`, `details`, `status_code`, `to_dict()`
- 11 subclasses: ValidationError, NotFoundError, UnauthorizedError, ForbiddenError, ConflictError, RateLimitError, ServiceUnavailableError, DatabaseError, ExternalServiceError, ConfigurationError, QuotaExceededError, PolicyViolationError
- Convenience functions: `not_found()`, `unauthorized()`, `forbidden()`, `bad_request()`, `conflict()`, `rate_limited()`, `service_unavailable()`

### 1.6 Structured Logging

**File**: `swx_core/middleware/logging_middleware.py`

- Logger: `logging.getLogger("SwX-API")`
- SOC 2 CC7.2 compliant structured JSON logging
- Fields: timestamp, level, message, request_id, user_id, ip, method, path, status_code, duration_ms, file, line
- Two formatters: `StructuredJSONFormatter` (production) and `TextFormatter` (development)
- Console handler (local only) + RotatingFileHandler (5MB, 10 backups)
- Log level mapping: debug→DEBUG, info→INFO, warning→WARNING, error→ERROR, critical→CRITICAL, production→WARNING

### 1.7 Background Tasks / Job System

Three distinct mechanisms:

**A. JobRunner** (`swx_core/services/job/job_runner.py`):
- Database-backed job queue with `SELECT ... FOR UPDATE SKIP LOCKED`
- Worker ID tracking (hostname-uuid)
- Exponential backoff retry (2^n seconds)
- Dead-letter queue for permanently failed jobs
- Configurable max concurrent jobs (default 10)
- Execution timeout (default 1 hour)
- Stale lock cleanup (default 5 min)

**B. Background asyncio tasks** (in `main.py` lifespan):
- `start_cache_refresh()` — translation cache refresh every 3600s
- `siem_batch_loop()` — SIEM event batching (conditional)
- `api_key_lifecycle_loop()` — expired API key cleanup
- `session_idle_cleanup_loop()` — idle session expiration

**C. Audit queue drain** (`swx_core/services/audit/audit_event_queue.py`):
- AsyncIO Queue with max 10,000 items
- Drops events on overflow with warning
- Drains in batches of 100
- 3 retry cycles on failure

**No distributed scheduler**: There is no declarative recurring job registration. All background tasks are manually started in the lifespan function with `asyncio.create_task()`.

### 1.8 Route Discovery

**File**: `swx_core/router.py`

Three-layer route loading:
1. **Core routes**: `dynamic_import()` scans `swx_core/routes/` at module load time
2. **Versioned app routes**: Scans `{app}/routes/{version}/` for each API_VERSION
3. **User routes**: Scans `{app}/routes/` recursively

Each module with a `router` (APIRouter) or `websocket_router` attribute gets auto-registered. Prefix derived from directory path or `ROUTE_PREFIX` module attribute. De-duplication via `_dedup_aggregated_packages()`.

**Import-time side effects**: Module loading triggers `load_all_modules()` at import time, which recursively imports ALL modules (models, services, repositories). This can trigger container resolution and service creation before the application is ready.

### 1.9 Health / Readiness

**File**: `swx_core/routes/utils/health_route.py`

- `GET /utils/health-check` — Simple `{"status": "healthy"}` (Docker/Kubernetes liveness)
- `GET /utils/health` — Database connectivity test

**Utility** (`swx_core/utils/health.py`):
- `HealthChecker` class with `add_check()`, `check_service()`, `check_all()`
- Built-in: `check_database()`, `check_redis()`, `check_celery()`, `check_external_service()`
- `HealthStatus` and `HealthCheckResult` models
- **Not wired to endpoints** — the HealthChecker class exists but is not used by the health routes

### 1.10 Configuration Validation

**File**: `swx_core/config/validation.py`

- `is_valid_config_value()` — rejects empty, placeholder (`<KEY>`, `${VAR}`), mock prefixes
- `is_valid_api_key()` — validates length after basic check
- `is_valid_dsn()` — validates DSN format
- `is_valid_redis_url()` — validates redis:// prefix
- `is_valid_webhook_secret()` — validates non-mock, length ≥ 8

**Runtime validation**:
- PII encryption key validation at startup (fail-closed)
- Audit log integrity check at startup (fail-closed)
- Settings via Pydantic `BaseSettings` with `env_file=".env"`

**No framework-level production validation**: There is no mechanism for applications to declare required secrets, forbidden localhost URLs, or incompatible configuration combinations.

### 1.11 Lifecycle Management

**No unified lifecycle manager**. Each background service is started independently in `main.py`'s `lifespan()`:

| Step | Service | Start | Stop |
|------|---------|-------|------|
| 6 | JobRunner | `await start_job_runner()` | None (no shutdown in lifespan) |
| 7 | Cache refresh | `start_cache_refresh()` | None (no shutdown) |
| 8 | Audit queue | `await audit_queue.start()` | `await audit_queue.stop()` |
| 9 | SIEM flush | `asyncio.create_task(siem_batch_loop())` | Task cancellation |
| 10 | API key lifecycle | `asyncio.create_task(api_key_lifecycle_loop())` | Task cancellation |
| 11 | Session cleanup | `asyncio.create_task(session_idle_cleanup_loop())` | Task cancellation |
| 12 | Redis event bridge | `await bridge.start()` | `await bridge.stop()` |

**Shutdown gaps**:
- JobRunner has no `await stop_job_runner()` in lifespan
- Cache refresh task is never cancelled
- Background tasks use `asyncio.gather(*tasks, return_exceptions=True)` but don't log individual failures

---

## 2. Gap Analysis

### 2.1 Feature Classification

| Requirement | Status | Details |
|-------------|--------|---------|
| **1. Bootstrap lifecycle** | ⚠️ Incomplete | Two conflicting paths, no stage logging, no timing, no circular dependency enforcement in providers |
| **2. Standard exception handling** | ⚠️ Implemented but incomplete | Handlers exist in `main.py` but are not reusable/extractable; production 500 may leak info; no correlation ID |
| **3. Middleware/security** | ⚠️ Implemented but inconsistent | 13 middleware exist but ordering is non-deterministic; no HSTS toggle per-env; no middleware configuration layer |
| **4. Structured logging** | ⚠️ Implemented but incomplete | Has request_id, method, path, status_code, duration_ms but missing: environment, service name, correlation ID, provider/bootstrap stage, lifecycle events |
| **5. Lifecycle service manager** | ❌ Missing | No unified lifecycle mechanism; each service manually started/stopped; no reverse-order shutdown; no failure identification |
| **6. Background task/scheduler** | ⚠️ Partially implemented | JobRunner exists for DB-backed jobs; no declarative registration; no recurring interval jobs; no multi-worker deduplication for asyncio tasks |
| **7. Production config validation** | ⚠️ Partially implemented | `config/validation.py` has validators but no framework-level `require()`/`forbid()`/`check()` mechanism for applications |
| **8. Route registration** | ⚠️ Implemented but has side effects | Auto-discovery works but imports all modules at load time; no separation of HTTP/WebSocket/webhook; import-time service creation |
| **9. Provider extension/DI** | ⚠️ Implemented but limited | Container supports `extend()` and contextual binding but apps use `patch_email_provider()`-style overrides; `defer` and `depends` declared but not enforced |
| **10. Health and readiness** | ⚠️ Implemented but incomplete | Liveness endpoint exists; `HealthChecker` class exists but not wired; no readiness endpoint; no dependency checking |
| **11. Thin entry point** | ❌ Missing | No `create_swx_app()` or equivalent; `main.py` has 370 lines of framework plumbing; apps must replicate all of it |
| **12. Backward compatibility** | N/A | To be evaluated during implementation |

### 2.2 Root Architectural Problems

**P1: Two conflicting initialization paths** (`main.py` vs `bootstrap_app()`)
- They don't compose. You must choose one or the other.
- `bootstrap_app()` doesn't set up lifespan services (job runner, audit queue, etc.)
- `main.py` doesn't use the container/provider system
- Result: apps either miss container services or miss lifecycle services

**P2: No deterministic middleware ordering**
- `load_middleware()` discovers middleware alphabetically by module name
- FastAPI middleware is LIFO (last added = outermost)
- Security-sensitive ordering (CORS outer, audit inner) is accidental
- No documented/ enforced ordering policy

**P3: Import-time side effects**
- `load_all_modules()` runs at module import time
- Route discovery (`swx_core/router.py`) loads all modules including services
- This can trigger container resolution and DB connections before the app is ready
- Makes testing and startup debugging difficult

**P4: No unified lifecycle management**
- Each background service is manually started with `asyncio.create_task()` or direct `await`
- No reverse-order shutdown
- No failure identification ("which service failed?")
- Shutdown gaps (JobRunner not stopped, cache refresh not cancelled)

**P5: No declarative background task registration**
- Job handlers must be manually registered one-by-one in lifespan
- No `swx.background.register(name=..., handler=..., interval=...)` pattern
- Recurring asyncio tasks are manually coded with `while True: ... await asyncio.sleep(N)`
- No graceful shutdown signal for recurring tasks

**P6: Provider `defer` and `depends` declared but unimplemented**
- `ServiceProvider.defer` flag exists but is never read
- `ServiceProvider.depends` list exists but is never enforced
- Circular provider dependencies can silently leave the framework partially initialized

**P7: Exception handlers coupled to `main.py`**
- 4 exception handlers are registered directly on the `app` object in `main.py`
- Cannot be reused without importing `main.py`
- Production 500 handler includes `request_id` but not `correlation_id`
- SwXError handler doesn't log the full traceback in production

---

## 3. Proposed Target Architecture

### 3.1 Unified Bootstrap with Deterministic Stages

```python
# swx_core/bootstrap.py (refactored)

class BootstrapStage(Enum):
    MODULE_DISCOVERY = "module_discovery"
    PROVIDER_REGISTRATION = "provider_registration"
    PROVIDER_BOOT = "provider_boot"
    CONTAINER_INITIALIZATION = "container_initialization"
    ROUTE_DISCOVERY = "route_discovery"
    MIDDLEWARE_SETUP = "middleware_setup"
    LIFECYCLE_SERVICES = "lifecycle_services"
    BACKGROUND_SERVICES = "background_services"
    APPLICATION_READY = "application_ready"

class BootstrapResult:
    stage_timings: dict[BootstrapStage, float]  # stage → duration in seconds
    stage_errors: dict[BootstrapStage, Exception]
    container: Container
    app: FastAPI

def bootstrap_app(
    app: FastAPI | None = None,
    *,
    title: str | None = None,
    app_name: str = "swx_app",
    providers: list[str] | None = None,
    discover_user_providers: bool = True,
    register_exception_handlers: bool = True,
    register_middleware: bool = True,
    register_routes: bool = True,
    register_lifespan_services: bool = True,
) -> BootstrapResult:
    """Deterministic bootstrap with stage logging and timing."""
    ...
```

**Key changes**:
- Each stage is a separate, logged, timed step
- Stages that fail produce clear error messages identifying the exact stage
- `BootstrapResult` contains timing data for observability
- The lifespan from `main.py` is absorbed into the framework
- Applications describe WHAT they want, not HOW to start it

### 3.2 Lifecycle Service Manager

```python
# swx_core/lifecycle.py (new)

class LifecycleService(ABC):
    name: str
    
    @abstractmethod
    async def start(self) -> None: ...
    
    @abstractmethod
    async def stop(self) -> None: ...

class LifecycleManager:
    def __init__(self):
        self._services: list[LifecycleService] = []
    
    def register(self, service: LifecycleService) -> None:
        self._services.append(service)
    
    async def start_all(self) -> None:
        """Start services in registration order. Fail fast with service name."""
        for service in self._services:
            start_time = time.monotonic()
            try:
                await service.start()
                logger.info(f"Lifecycle service started: {service.name} ({time.monotonic()-start_time:.2f}s)")
            except Exception as e:
                raise LifecycleError(f"Failed to start {service.name}: {e}") from e
    
    async def stop_all(self) -> None:
        """Stop services in reverse registration order. Best-effort."""
        for service in reversed(self._services):
            try:
                await service.stop()
            except Exception as e:
                logger.error(f"Failed to stop {service.name}: {e}")
```

**Built-in services**:
- `JobRunnerService` — wraps existing `JobRunner`
- `AuditQueueService` — wraps `audit_queue.start()/stop()`
- `CacheRefreshService` — wraps cache refresh with proper shutdown
- `RedisBridgeService` — wraps `RedisEventBridge.start()/stop()`
- `SIEMFlushService` — wraps SIEM batch loop
- `APIKeyLifecycleService` — wraps API key cleanup
- `SessionCleanupService` — wraps session idle cleanup

### 3.3 Background Task / Scheduler Abstraction

```python
# swx_core/background.py (refactored)

class BackgroundScheduler:
    """Declarative recurring task scheduler with graceful shutdown."""
    
    def register(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        interval: int,  # seconds
        *,
        startup: bool = True,
        error_policy: str = "log_and_continue",  # or "raise"
    ) -> None: ...
    
    async def start(self) -> None: ...
    async def stop(self, timeout: float = 30.0) -> None: ...
```

**Multi-worker safety**: The existing `JobRunner` with `SELECT ... FOR UPDATE SKIP LOCKED` already provides distributed job execution safety. The new `BackgroundScheduler` is for **in-process recurring tasks** (like cache refresh, session cleanup) that run on every worker. For tasks that must only run once across all workers, applications should use `enqueue_job()` which has built-in distributed locking.

### 3.4 Standard Exception Handlers (Extracted)

```python
# swx_core/exceptions/handlers.py (new)

def register_exception_handlers(app: FastAPI) -> None:
    """Register standard SWX exception handlers on a FastAPI app."""
    
    @app.exception_handler(SwXError)
    async def swx_error_handler(request: Request, exc: SwXError) -> JSONResponse:
        ...
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
        ...
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        ...
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Production: never leak internal details
        # Development: include traceback in response
        ...
```

### 3.5 Middleware Configuration Layer

```python
# swx_core/middleware/stack.py (new)

class MiddlewareStack:
    """Ordered middleware configuration with documented security implications."""
    
    # Middleware order matters! Listed in APPLICATION order (first = outermost).
    # FastAPI internally reverses this, so the last added runs first.
    
    MIDDLEWARE_ORDER = [
        # 1. CORS (outermost — must be first to handle preflight)
        ("cors", CORSMiddleware, True),
        # 2. Security headers (adds X-Request-ID, HSTS, CSP, etc.)
        ("security_headers", SecurityHeadersMiddleware, True),
        # 3. Audit middleware (assigns request ID for correlation)
        ("audit", AuditMiddleware, True),
        # 4. Logging (structured request/response logging)
        ("logging", LoggingMiddleware, True),
        # 5. Rate limiting (per-user/IP rate limiting)
        ("rate_limit", RateLimitMiddleware, True),
        # 6. Auth rate limiting (path-aware auth rate limiting)
        ("auth_rate_limit", AuthRateLimitMiddleware, True),
        # 7. Rate limit headers (X-RateLimit-* response headers)
        ("rate_limit_headers", RateLimitHeadersMiddleware, True),
        # 8. Tenant context (extracts tenant_id)
        ("tenant", TenantContextMiddleware, True),
        # 9. CSRF protection (cookie-based double-submit)
        ("csrf", CSRFMiddleware, True),
        # 10. Container scope (per-request DI scope)
        ("container", ContainerMiddleware, True),
        # 11. Session (cookie-based sessions)
        ("session", None, True),  # setup_session_middleware called separately
        # 12. Metrics (Prometheus) — optional
        ("metrics", MetricsMiddleware, False),
        # 13. Sentry (error tracking) — optional
        ("sentry", None, False),  # SDK init, not ASGI middleware
    ]
    
    def apply(self, app: FastAPI, *, overrides: dict | None = None) -> None:
        """Apply middleware in correct order with per-app customization."""
        ...
```

### 3.6 Structured Logging Enhancement

```python
# swx_core/middleware/logging_middleware.py (enhanced)

# Additional structured fields:
# - environment: from settings.ENVIRONMENT
# - service_name: from settings.PROJECT_NAME
# - correlation_id: from X-Correlation-ID header or generated
# - provider_stage: set during bootstrap
# - lifecycle_event: startup/shutdown stage names
```

### 3.7 Production Configuration Validation

```python
# swx_core/config/validator.py (new)

class ProductionValidator:
    """Extensible production configuration validation."""
    
    def require(self, env_var: str, message: str | None = None) -> 'ProductionValidator':
        """Fail if env var is missing or is a placeholder."""
        ...
    
    def forbid_localhost(self, env_var: str, message: str | None = None) -> 'ProductionValidator':
        """Fail if env var contains localhost/127.0.0.1 in production."""
        ...
    
    def check(self, condition: Callable[[], bool], message: str) -> 'ProductionValidator':
        """Fail if condition is False in production."""
        ...
    
    def validate(self, environment: str = "production") -> list[str]:
        """Run all checks. Returns list of errors. Raises in production."""
        ...

# Usage in app:
validator = ProductionValidator()
validator.require("STRIPE_API_KEY")
validator.require("DEVICE_ENROLLMENT_SECRET")
validator.forbid_localhost("DOWNLOAD_BASE_URL")
validator.check(lambda: settings.BILLING_ENABLED or not settings.STRIPE_API_KEY,
                "STRIPE_API_KEY set but billing disabled")
```

### 3.8 Health and Readiness

```python
# swx_core/routes/utils/health_route.py (enhanced)

@router.get("/health", tags=["Health"])
async def health_detailed(session: AsyncSession = Depends(get_session)):
    """Readiness check with dependency status."""
    checker = HealthChecker()
    checker.add_check("database", check_database)
    if settings.REDIS_ENABLED:
        checker.add_check("redis", check_redis)
    # Applications can add their own checks via lifecycle
    result = await checker.check_all()
    status_code = 200 if result.status == "healthy" else 503
    return JSONResponse(content=result.dict(), status_code=status_code)

@router.get("/health-check", tags=["Health"])
async def health_check():
    """Liveness check — always returns healthy if the process is alive."""
    return {"status": "healthy", "service": settings.PROJECT_NAME}
```

### 3.9 Thin Application Entry Point

```python
# Target API for applications (e.g., qiro_app/main.py):

from swx_core import create_swx_app, bootstrap_app
from swx_core.config.settings import settings

app = create_swx_app(
    title=settings.PROJECT_NAME,
    app_name="qiro_app",
)

# Application-specific setup
from qiro_app.providers import AppServiceProvider
from qiro_app.listeners import register_listeners

app.register_provider(AppServiceProvider)
register_listeners(app)

# Production validation
from swx_core.config.validator import ProductionValidator
validator = ProductionValidator()
validator.require("STRIPE_API_KEY")
validator.forbid_localhost("DOWNLOAD_BASE_URL")
app.set_production_validator(validator)

# Bootstrap
container = bootstrap_app(app)
```

---

## 4. Files/Modules That Need Modification

### New Files (to create)

| File | Purpose |
|------|---------|
| `swx_core/lifecycle.py` | LifecycleService, LifecycleManager |
| `swx_core/background.py` | BackgroundScheduler (replaces `background_task.py`) |
| `swx_core/exceptions/__init__.py` | Exception package |
| `swx_core/exceptions/handlers.py` | Extracted exception handlers from `main.py` |
| `swx_core/middleware/stack.py` | Ordered middleware configuration |
| `swx_core/config/validator.py` | ProductionValidator |

### Files to Modify (significant)

| File | Changes |
|------|---------|
| `swx_core/bootstrap.py` | Refactor to unified deterministic stages with timing/logging; absorb lifespan from `main.py` |
| `swx_core/main.py` | Simplify to use `create_swx_app()` + `bootstrap_app()`; remove manual lifespan steps |
| `swx_core/providers/base.py` | Enforce `depends` declarations; detect circular provider dependencies; implement deferred loading |
| `swx_core/middleware/logging_middleware.py` | Add environment, service name, correlation ID, bootstrap stage, lifecycle event fields |
| `swx_core/container/container.py` | Add `has()` alias for `bound()`; add `override()` method for explicit provider replacement |
| `swx_core/config/validation.py` | Extend with ProductionValidator framework |
| `swx_core/routes/utils/health_route.py` | Wire HealthChecker; add readiness endpoint |
| `swx_core/utils/health.py` | Make HealthChecker async-aware; add Redis/bridge checks |

### Files to Deprecate (not delete immediately)

| File | Reason |
|------|--------|
| `swx_core/background_task.py` | Replaced by `swx_core/background.py` BackgroundScheduler |

### Test Files to Create

| File | Tests |
|------|-------|
| `tests/bootstrap/test_bootstrap_lifecycle.py` | Stage ordering, timing, error identification, circular dependency detection |
| `tests/bootstrap/test_lifecycle_manager.py` | Start/stop ordering, reverse-order shutdown, failure identification |
| `tests/bootstrap/test_background_scheduler.py` | Job registration, cancellation, graceful shutdown, interval configuration |
| `tests/middleware/test_middleware_stack.py` | Middleware ordering verification |
| `tests/exceptions/test_handlers.py` | SwXError handler, validation handler, HTTP handler, generic handler, production 500 no-leak |
| `tests/config/test_production_validator.py` | require, forbid_localhost, check, production-only validation |
| `tests/bootstrap/test_route_discovery.py` | Import-time side effect verification, HTTP/WebSocket/webhook registration |
| `tests/bootstrap/test_provider_override.py` | Container override, extend, contextual binding |

---

## 5. Migration / Compatibility Risks

| Risk | Mitigation |
|------|-----------|
| `main.py` is the existing entry point — changing it breaks all deployments | Keep `main.py` working; provide `create_swx_app()` as new preferred path; `main.py` internally calls `create_swx_app()` |
| Exception handlers are registered on `app` directly — extracting them changes behavior | `register_exception_handlers(app)` called from bootstrap; same behavior, just extracted |
| Middleware ordering change may break existing apps | `MiddlewareStack.apply()` defaults to current behavior; `overrides` parameter for customization |
| `bootstrap_app()` signature changes | Keep backward-compatible signature; add keyword-only parameters |
| `lifespan()` function is replaced by `LifecycleManager` | Existing `lifespan()` continues to work; `LifecycleManager` is opt-in via `create_swx_app()` |
| `background_task.py` deprecation | Keep module as thin wrapper around new `BackgroundScheduler`; add deprecation warning |
| Container `override()` is new — existing `singleton()` override still works | Both mechanisms work; `override()` is explicit and recommended |
| Health endpoint changes | New `/health/readiness` endpoint; existing `/health` and `/health-check` unchanged |

---

## 6. Phased Implementation Plan

### Phase 1: Foundation (bootstrap, exceptions, middleware, logging)

**Goal**: Deterministic startup, reusable error handling, ordered middleware, structured logging.

1. **Refactor `bootstrap.py`**: Deterministic stages, timing, structured logging per stage, circular dependency detection
2. **Extract exception handlers to `swx_core/exceptions/handlers.py`**: Make them reusable, add production 500 protection, add correlation ID
3. **Create `swx_core/middleware/stack.py`**: Ordered middleware configuration with documented order
4. **Enhance structured logging**: Add environment, service name, correlation ID, bootstrap stage fields
5. **Tests**: bootstrap ordering, exception handlers, middleware ordering

### Phase 2: Lifecycle and Background Tasks

**Goal**: Unified lifecycle management, declarative background task registration, production config validation.

1. **Create `swx_core/lifecycle.py`**: `LifecycleService` + `LifecycleManager` with reverse-order shutdown
2. **Create `swx_core/background.py`**: `BackgroundScheduler` with declarative registration, graceful shutdown
3. **Create `swx_core/config/validator.py`**: `ProductionValidator` with `require`/`forbid_localhost`/`check`
4. **Migrate existing lifespan services to LifecycleService implementations**
5. **Tests**: lifecycle start/stop ordering, background scheduler, config validation

### Phase 3: Application API and Provider Extensions

**Goal**: Thin entry point, provider override mechanism, health/readiness, route improvements.

1. **Create `create_swx_app()`**: Factory function that sets up app, middleware, exception handlers, routes
2. **Add `container.override()`**: Explicit provider replacement mechanism
3. **Enforce `ServiceProvider.depends`**: Validate provider dependencies at registration time
4. **Enhance health/readiness**: Wire HealthChecker, add readiness endpoint
5. **Route discovery**: Separate route registration from module loading to avoid import-time side effects
6. **Tests**: provider override, thin entry point, health checks, route discovery

---

## 7. Success Criteria

The final result must make SWX Core:

- **Deterministic**: Startup stages are ordered, timed, and logged. Failures identify the exact stage and service.
- **Observable**: Structured logging covers every lifecycle event with correlation IDs.
- **Fail-fast**: Circular dependencies detected. Production config validated. No partial initialization.
- **Testable**: Each stage can be tested independently. Mock providers can replace real ones.
- **Extensible**: Applications override services cleanly via the container. No `patch_*` functions.
- **Thin**: Application `main.py` files describe behavior, not framework plumbing.

The canonical application entry point should be under 20 lines of application-specific code.