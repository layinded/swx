"""
Main Application Entry Point
----------------------------
This module initializes the FastAPI application with:
- Database setup and initial data seeding.
- Dynamic module and middleware loading.
- Background tasks (e.g., cache refresh).
- Custom exception handlers for better error handling.

Lifecycle:
- On startup:
    1. Runs database migrations and superuser creation.
    2. Seeds initial data (e.g., translations, languages).
    3. Starts background tasks (e.g., cache refresh).
- On shutdown:
    - Graceful application shutdown logic.

Exception Handling:
- Handles HTTP exceptions with proper logging.
- Captures request validation errors.
- Provides a fallback handler for unexpected errors.

"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from swx_core.background_task import start_cache_refresh
from swx_core.config.settings import settings
from swx_core.database.db_setup import setup_database
from swx_core.middleware.logging_middleware import logger
from swx_core.router import router
from swx_core.utils.errors import SwXError
from swx_core.utils.loader import load_all_modules, load_middleware
from swx_core.database.db_seed import seed_data
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource

# Initial load of all modules on startup
loaded_modules = load_all_modules()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa
    """
    Application startup and shutdown lifecycle events.

    On Startup:
        - Runs database setup (migrations and superuser creation).
        - Seeds initial data (e.g., translations, languages).
        - Starts background tasks like cache refresh.

    On Shutdown:
        - Logs shutdown event.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is passed to the application.
    """
    logger.info("Initializing application startup...")

    # Step 0a: Validate encryption key when PII encryption is enabled (fail-closed)
    if settings.PII_ENCRYPTION_ENABLED:
        from swx_core.security.encryption import validate_encryption_key
        try:
            validate_encryption_key()
            logger.info("Encryption key validated successfully (PII encryption enabled).")
        except Exception as e:
            await alert_engine.emit(
                severity=AlertSeverity.CRITICAL,
                source=AlertSource.SYSTEM,
                event_type="STARTUP_FAILURE_ENCRYPTION",
                message=f"Application failed to start: PII encryption enabled but encryption key is invalid: {e}",
                metadata={"error": str(e)},
            )
            raise

    # Step 1: Run Database Setup (Migrations & Superuser Creation)
    # When DOCKERIZED, prestart has already run db_setup (alembic + superuser + seed).
    # Skip here to avoid duplicate migrations (e.g. "type jobstatus already exists") and
    # redundant seeding. Each worker would otherwise run setup_database.
    if not settings.DOCKERIZED:
        logger.info("Running database setup (migrations and superuser creation)...")
        try:
            await setup_database()
            logger.info("Database setup completed successfully.")
        except Exception as e:
            await alert_engine.emit(
                severity=AlertSeverity.CRITICAL,
                source=AlertSource.SYSTEM,
                event_type="STARTUP_FAILURE_DB",
                message=f"Application failed to start due to database setup error: {e}",
                metadata={"error": str(e)}
            )
            raise e

        # Step 2: Seed initial data
        logger.info("Seeding initial data (translations, languages, etc.)...")
        await seed_data()
        logger.info("Initial data seeded successfully.")
    else:
        logger.info("DOCKERIZED=true: skipping setup_database and seed_data (handled by prestart).")

    # Step 2b: Verify audit log hash chain integrity (SOC 2 CC7.2, fail-closed)
    # Must run AFTER database setup so the audit_log table exists on fresh installs.
    try:
        from swx_core.database.db import async_session
        from swx_core.services.compliance.audit_integrity_service import check_startup_integrity
        async with async_session() as integrity_session:
            await check_startup_integrity(integrity_session)
        logger.info("Audit log integrity verified at startup.")
    except Exception as e:
        logger.critical("Audit log integrity check FAILED at startup: %s", e)
        await alert_engine.emit(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            event_type="STARTUP_FAILURE_AUDIT_INTEGRITY",
            message=f"Application failed to start: audit log integrity check failed: {e}",
            metadata={"error": str(e)},
        )
        raise

    # Step 3: Register system policies
    logger.info("Registering system policies...")
    from swx_core.services.policy.policy_registry import register_system_policies
    register_system_policies()
    logger.info("System policies registered successfully.")

    # Step 4: Register job handlers
    logger.info("Registering job handlers...")
    from swx_core.services.job import register_job_handler
    from swx_core.services.job.handlers import (
        billing_sync_handler,
        billing_webhook_handler,
        alert_send_handler,
        audit_aggregate_handler,
        cache_refresh_handler,
        compliance_data_subject_delete_handler,
        compliance_retention_apply_handler,
        compliance_api_key_expired_cleanup_handler,
        compliance_session_idle_cleanup_handler,
    )
    from swx_core.models.job import JobType
    
    register_job_handler(JobType.billing_sync, billing_sync_handler)
    register_job_handler(JobType.billing_webhook, billing_webhook_handler)
    register_job_handler(JobType.alert_send, alert_send_handler)
    register_job_handler(JobType.audit_aggregate, audit_aggregate_handler)
    register_job_handler(JobType.cache_refresh, cache_refresh_handler)
    register_job_handler(JobType.compliance_data_subject_delete, compliance_data_subject_delete_handler)
    register_job_handler(JobType.compliance_retention_apply, compliance_retention_apply_handler)
    register_job_handler(JobType.compliance_api_key_expired_cleanup, compliance_api_key_expired_cleanup_handler)
    register_job_handler(JobType.compliance_session_idle_cleanup, compliance_session_idle_cleanup_handler)
    logger.info("Job handlers registered successfully.")

    # Step 5: Register webhook bridge (domain events -> outbound webhooks)
    logger.info("Registering webhook bridge listener...")
    from swx_core.events.listeners.webhook_bridge_listener import register_webhook_bridge
    register_webhook_bridge()
    logger.info("Webhook bridge listener registered successfully.")

    # Step 6: Start job runner
    logger.info("Starting job runner...")
    from swx_core.services.job import start_job_runner
    await start_job_runner()
    logger.info("Job runner started successfully.")

    # Step 7: Start background tasks (e.g., cache refresh)
    logger.info("Starting cache refresh background task.")
    start_cache_refresh()

    # Step 8: Start audit event queue drain worker
    from swx_core.services.audit.audit_event_queue import audit_queue
    await audit_queue.start()

    # Step 9: Start SIEM batch flush worker (SOC 2 CC7.2)
    import asyncio
    _bg_tasks: list[asyncio.Task[None]] = []

    if settings.SIEM_ENABLED:  # pyright: ignore[reportAttributeAccessIssue]
        from swx_core.services.compliance.siem_service import siem_batch_loop
        _siem_task = asyncio.create_task(siem_batch_loop())
        _bg_tasks.append(_siem_task)
        logger.info("SIEM batch flush worker started (interval=%ss).", settings.SIEM_BATCH_INTERVAL)

    # Step 10: Start API key lifecycle cleanup worker (SOC 2 CC6.1)
    from swx_core.services.compliance.api_key_lifecycle_service import api_key_lifecycle_loop
    _api_key_task = asyncio.create_task(api_key_lifecycle_loop())
    _bg_tasks.append(_api_key_task)
    logger.info("API key lifecycle cleanup worker started (interval=%ss).", settings.API_KEY_LIFECYCLE_INTERVAL_SECONDS)

    # Step 11: Start idle session cleanup worker (SOC 2 CC6.1)
    from swx_core.services.auth.session_service import session_idle_cleanup_loop
    _session_task = asyncio.create_task(session_idle_cleanup_loop())
    _bg_tasks.append(_session_task)
    logger.info("Idle session cleanup worker started (interval=%ss).", settings.SESSION_IDLE_CLEANUP_INTERVAL_SECONDS)

    # Step 12: Start Redis event bridge for cross-worker broadcasting
    from swx_core.container.container import get_container
    from swx_core.events.redis_bridge import RedisEventBridge

    container = get_container()
    bridge: RedisEventBridge | None = None
    if container.bound("event_bridge"):
        bridge = container.make("event_bridge")
        await bridge.start()
        logger.info("Redis event bridge started — cross-worker event broadcasting active.")
    else:
        logger.debug("Redis event bridge skipped (REDIS_ENABLED=False or EVENT_BRIDGE_ENABLED=False). Events stay in-process.")

    # Yield control to the application (it will run until shutdown)
    yield

    # Shutdown: cancel background tasks
    for t in _bg_tasks:
        t.cancel()
    if _bg_tasks:
        await asyncio.gather(*_bg_tasks, return_exceptions=True)
        logger.info("Cancelled %d background tasks.", len(_bg_tasks))

    # Stop Redis event bridge
    if bridge is not None:
        await bridge.stop()
        logger.info("Redis event bridge stopped.")

    await audit_queue.stop()
    logger.info("Shutting down application...")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.ROUTE_PREFIX}/openapi.json",
    lifespan=lifespan,
)


# Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc):
    """
    Handles HTTP exceptions and logs structured error messages.

    Args:
        request (Request): The incoming request object.
        exc (StarletteHTTPException): The HTTP exception.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    logger.error("HTTP ERROR: %s - Path: %s", exc.detail, request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 422 with sanitized error details, surviving non-serializable body types (FormData, UploadFile, bytes)."""
    logger.warning("Validation error at %s: %s", request.url.path, exc.errors())

    from fastapi.encoders import jsonable_encoder
    from swx_core.utils.json import dumps as swx_dumps

    safe_body = None
    if hasattr(exc, 'body'):
        try:
            safe_body = jsonable_encoder(exc.body)
        except Exception:
            safe_body = None

    try:
        safe_detail = jsonable_encoder(exc.errors())
    except Exception:
        safe_detail = [
            {"type": e.get("type"), "msg": e.get("msg"), "loc": e.get("loc")}
            for e in exc.errors()
        ]

    try:
        serialized = swx_dumps({"detail": safe_detail, "body": safe_body})
        return Response(content=serialized, status_code=422, media_type="application/json")
    except Exception:
        logger.exception("Failed to serialize validation error response")
        minimal_detail = [
            {"type": e.get("type"), "msg": e.get("msg"), "loc": e.get("loc")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": minimal_detail, "body": None})


@app.exception_handler(SwXError)
async def swx_error_handler(request: Request, exc: SwXError):
    """Handle SwXError subclasses and return structured JSON error responses."""
    logger.warning("SwXError at %s: [%s] %s", request.url.path, exc.code, exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handles unexpected exceptions and logs critical errors.

    Args:
        request (Request): The incoming request object.
        exc (Exception): The unhandled exception.

    Returns:
        JSONResponse: A generic internal server error response.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.critical("Unhandled exception at %s: %s (request_id=%s)", request.url.path, type(exc).__name__, request_id)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "request_id": request_id},
    )


# Load and apply middleware dynamically
load_middleware(app)

# Include API Routes
app.include_router(router)


# Root Endpoint
@app.get("/")
def read_root():
    """
    Root endpoint to verify API is running.

    Returns:
        dict: A welcome message.
    """
    return {"message": "Welcome to swX API 🚀"}