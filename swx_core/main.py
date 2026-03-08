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

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from swx_core.background_task import start_cache_refresh
from swx_core.config.settings import settings
from swx_core.database.db_setup import setup_database
from swx_core.middleware.logging_middleware import logger
from swx_core.router import router
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
    )
    from swx_core.models.job import JobType
    
    register_job_handler(JobType.billing_sync, billing_sync_handler)
    register_job_handler(JobType.billing_webhook, billing_webhook_handler)
    register_job_handler(JobType.alert_send, alert_send_handler)
    register_job_handler(JobType.audit_aggregate, audit_aggregate_handler)
    register_job_handler(JobType.cache_refresh, cache_refresh_handler)
    logger.info("Job handlers registered successfully.")

    # Step 5: Start job runner
    logger.info("Starting job runner...")
    from swx_core.services.job import start_job_runner
    await start_job_runner()
    logger.info("Job runner started successfully.")

    # Step 6: Start background tasks (e.g., cache refresh)
    logger.info("Starting cache refresh background task.")
    start_cache_refresh()

    # Yield control to the application (it will run until shutdown)
    yield

    # Shutdown logic (if needed)
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
    logger.error(f"HTTP ERROR: {exc.detail} - Path: {request.url.path}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    """
    Handles request validation errors and logs structured error messages.

    Args:
        request (Request): The incoming request object.
        exc (RequestValidationError): The validation error exception.

    Returns:
        JSONResponse: A JSON response with validation error details.
    """
    logger.error(f"VALIDATION ERROR: {exc.errors()} - Path: {request.url.path}")
    return JSONResponse(status_code=422, content={"error": "Validation Error"})


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
    logger.critical(f"UNHANDLED EXCEPTION: {exc} - Path: {request.url.path}")
    return JSONResponse(status_code=500, content={"error": "Internal Server Error"})


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