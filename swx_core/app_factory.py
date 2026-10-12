"""
SwX Application Factory
------------------------
Create a fully-configured FastAPI application with one call.

``create_swx_app()`` replaces the 370-line ``main.py`` with a declarative
entry point.  It wires up:

* Deterministic bootstrap (providers, routes, hooks, listeners)
* Structured exception handlers (production-safe)
* Ordered middleware stack (security-correct)
* Lifecycle service manager (start in order, stop in reverse)
* Background scheduler (declarative recurring tasks)
* Production configuration validation

Usage (thin application entry point)::

    from swx_core import create_swx_app

    app = create_swx_app(
        title="QiroPrint API",
        app_name="qiro_app",
    )

    # Register application-specific behaviour:
    from qiro_app.providers import AppServiceProvider
    from swx_core.bootstrap import bootstrap_app

    container = bootstrap_app(app)

Applications that need the legacy ``main.py`` behaviour can continue
to import it directly — this factory is the recommended path forward.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI

from swx_core.config.settings import settings
from swx_core.exceptions.handlers import register_exception_handlers
from swx_core.lifecycle import LifecycleManager, LifecycleService
from swx_core.middleware.logging_middleware import logger
from swx_core.middleware.stack import apply_middleware_stack
from swx_core.router import router


# ---------------------------------------------------------------------------
# Built-in lifecycle services
# ---------------------------------------------------------------------------


class JobRunnerService(LifecycleService):
    """Start and stop the background job runner."""

    name = "job_runner"

    async def start(self) -> None:
        from swx_core.services.job import start_job_runner
        await start_job_runner()

    async def stop(self) -> None:
        from swx_core.services.job import stop_job_runner
        try:
            await stop_job_runner()
        except Exception:
            logger.exception("lifecycle.stop_failed service=%s", self.name)


class AuditQueueService(LifecycleService):
    """Start and stop the audit event queue drain worker."""

    name = "audit_queue"

    async def start(self) -> None:
        from swx_core.services.audit.audit_event_queue import audit_queue
        await audit_queue.start()

    async def stop(self) -> None:
        from swx_core.services.audit.audit_event_queue import audit_queue
        await audit_queue.stop()


class RedisBridgeService(LifecycleService):
    """Start and stop the Redis event bridge for cross-worker events."""

    name = "redis_event_bridge"

    def __init__(self) -> None:
        self._bridge: Any = None

    async def start(self) -> None:
        if not settings.REDIS_ENABLED or not settings.EVENT_BRIDGE_ENABLED:
            logger.info("lifecycle.skip service=%s (disabled)", self.name)
            return

        from swx_core.container.container import get_container
        from swx_core.events.dispatcher import event_bus

        container = get_container()
        bridge = None

        if container.bound("event_bridge"):
            try:
                bridge = container.make("event_bridge")
            except Exception as exc:
                logger.warning("Failed to create event bridge from container: %s", exc)

        if bridge is None:
            try:
                redis_client = None
                if container.bound("redis.client"):
                    redis_client = container.make("redis.client")

                if redis_client is not None:
                    from swx_core.events.redis_bridge import RedisEventBridge

                    bridge = RedisEventBridge(
                        event_bus=event_bus,
                        redis_client=redis_client,
                        channel_prefix=settings.EVENT_BRIDGE_CHANNEL_PREFIX,
                        app_name=RedisEventBridge.default_app_name(settings.PROJECT_NAME),
                    )
                    bridge.patch_dispatch()
            except Exception as exc:
                logger.warning("Could not create event bridge directly: %s", exc)

        if bridge is not None:
            await bridge.start()
            self._bridge = bridge
            logger.info("lifecycle.started service=%s", self.name)
        else:
            logger.debug("Redis event bridge skipped (unavailable or disabled)")

    async def stop(self) -> None:
        if self._bridge is not None:
            await self._bridge.stop()
            self._bridge = None


# ---------------------------------------------------------------------------
# Lifespan builder
# ---------------------------------------------------------------------------


def _build_lifespan(lifecycle: LifecycleManager) -> Any:
    """Build an async context manager that runs lifecycle services."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[misc]
        logger.info("lifespan.starting")
        # --- Startup validation ---
        if settings.PII_ENCRYPTION_ENABLED:
            from swx_core.security.encryption import validate_encryption_key
            validate_encryption_key()
            logger.info("Encryption key validated (PII encryption enabled).")

        # --- Database setup (skip in Docker — prestart script handles it) ---
        if not settings.DOCKERIZED:
            from swx_core.database.db_setup import setup_database
            await setup_database()
            logger.info("Database setup completed.")

            from swx_core.database.db_seed import seed_data
            await seed_data()
            logger.info("Initial data seeded.")

        # --- Audit integrity (SOC 2 CC7.2) ---
        from swx_core.database.db import async_session
        from swx_core.services.compliance.audit_integrity_service import check_startup_integrity
        async with async_session() as integrity_session:
            await check_startup_integrity(integrity_session)
        logger.info("Audit log integrity verified.")

        # --- System policies ---
        from swx_core.services.policy.policy_registry import register_system_policies
        register_system_policies()
        logger.info("System policies registered.")

        # --- Job handlers ---
        _register_core_job_handlers()

        # --- Webhook bridge ---
        from swx_core.events.listeners.webhook_bridge_listener import register_webhook_bridge
        register_webhook_bridge()
        logger.info("Webhook bridge listener registered.")

        # --- Start lifecycle services ---
        await lifecycle.start_all()

        yield  # --- Application is running ---

        # --- Shutdown ---
        logger.info("lifespan.shutting_down")
        await lifecycle.stop_all()
        logger.info("lifespan.shutdown_complete")

    return lifespan


def _register_core_job_handlers() -> None:
    """Register the standard set of job handlers."""
    from swx_core.services.job import register_job_handler
    from swx_core.services.job.handlers import (
        alert_send_handler,
        audit_aggregate_handler,
        billing_sync_handler,
        billing_webhook_handler,
        cache_refresh_handler,
        compliance_api_key_expired_cleanup_handler,
        compliance_data_subject_delete_handler,
        compliance_retention_apply_handler,
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
    logger.info("Core job handlers registered.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_swx_app(
    title: Optional[str] = None,
    app_name: str = "swx_app",
    *,
    register_routes: bool = True,
    register_middleware: bool = True,
    register_exception_handlers: bool = True,
    middleware_overrides: Optional[dict[str, bool]] = None,
    lifecycle_services: Optional[list[LifecycleService]] = None,
    providers: Optional[list[str]] = None,
    discover_user_providers: bool = True,
    validate_production_config: bool = True,
) -> FastAPI:
    """Create a fully-configured SwX FastAPI application.

    This factory handles all framework plumbing so application entry points
    can be thin and declarative.

    Args:
        title: Application title (defaults to ``settings.PROJECT_NAME``).
        app_name: Application module name for discovery (defaults to
            ``"swx_app"``).  Set ``SWX_APP_NAME`` env var instead for
            runtime configuration.
        register_routes: Whether to include auto-discovered routes.
        register_middleware: Whether to apply the canonical middleware stack.
        register_exception_handlers: Whether to register standard handlers.
        middleware_overrides: Per-middleware enable/disable overrides.
        lifecycle_services: Additional ``LifecycleService`` instances to
            manage alongside the built-in ones.
        providers: Additional provider class paths to register.
        discover_user_providers: Whether to auto-discover app providers.
        validate_production_config: Whether to run production config checks.

    Returns:
        A ``FastAPI`` application ready for ``uvicorn``.
    """
    from swx_core.config.discovery import DiscoveryConfig, reset_discovery

    # Reconfigure discovery if app_name differs from default.
    if app_name != "swx_app":
        reset_discovery(app_name=app_name)

    title = title or settings.PROJECT_NAME

    # --- Production config validation ---
    if validate_production_config:
        from swx_core.config.validator import ProductionValidator
        validator = ProductionValidator()
        errors = validator.validate(environment=settings.ENVIRONMENT)
        if errors:
            for error in errors:
                logger.critical("production_config.invalid: %s", error)
            if settings.ENVIRONMENT in ("production", "prod"):
                raise SystemExit(1)

    # --- Build lifecycle manager ---
    lifecycle = LifecycleManager()
    lifecycle.register(JobRunnerService())
    lifecycle.register(AuditQueueService())
    lifecycle.register(RedisBridgeService())

    # SIEM batch flush (conditional)
    if getattr(settings, "SIEM_ENABLED", False):
        lifecycle.register(_SIEMFlushService())

    # API key lifecycle cleanup
    lifecycle.register(_APIKeyLifecycleService())

    # Idle session cleanup
    lifecycle.register(_SessionCleanupService())

    # Cache refresh (legacy task — registered via background scheduler)
    lifecycle.register(_CacheRefreshService())

    # User-provided lifecycle services.
    if lifecycle_services:
        for svc in lifecycle_services:
            lifecycle.register(svc)

    # --- Create FastAPI app ---
    app = FastAPI(
        title=title,
        openapi_url=f"{settings.ROUTE_PREFIX}/openapi.json",
        lifespan=_build_lifespan(lifecycle),
    )

    # Store environment for exception handlers.
    app.state.environment = settings.ENVIRONMENT

    # Store health checker for /health and /ready endpoints.
    from swx_core.utils.health import get_health_checker
    app.state.health_checker = get_health_checker(version=settings.VERSION)

    # --- Exception handlers ---
    if register_exception_handlers:
        from swx_core.exceptions.handlers import register_exception_handlers
        register_exception_handlers(app)

    # --- Middleware stack ---
    if register_middleware:
        apply_middleware_stack(app, overrides=middleware_overrides)

    # --- Routes ---
    if register_routes:
        app.include_router(router)

    # --- Bootstrap (providers, hooks, listeners) ---
    from swx_core.bootstrap import bootstrap_app
    bootstrap_app(app, providers=providers, discover_user_providers=discover_user_providers, register_middleware=False)

    # Root endpoint
    @app.get("/")
    def root():
        return {"message": f"Welcome to {title}"}

    return app


# ---------------------------------------------------------------------------
# Additional lifecycle services (small wrappers)
# ---------------------------------------------------------------------------


class _SIEMFlushService(LifecycleService):
    name = "siem_batch_flush"

    async def start(self) -> None:
        import asyncio
        from swx_core.services.compliance.siem_service import siem_batch_loop
        self._task = asyncio.create_task(siem_batch_loop())
        logger.info("lifecycle.started service=%s interval=%ds", self.name, getattr(settings, "SIEM_BATCH_INTERVAL", 60))

    async def stop(self) -> None:
        if hasattr(self, "_task") and self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass


class _APIKeyLifecycleService(LifecycleService):
    name = "api_key_lifecycle"

    async def start(self) -> None:
        import asyncio
        from swx_core.services.compliance.api_key_lifecycle_service import api_key_lifecycle_loop
        self._task = asyncio.create_task(api_key_lifecycle_loop())
        logger.info("lifecycle.started service=%s", self.name)

    async def stop(self) -> None:
        if hasattr(self, "_task") and self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass


class _SessionCleanupService(LifecycleService):
    name = "session_idle_cleanup"

    async def start(self) -> None:
        import asyncio
        from swx_core.services.auth.session_service import session_idle_cleanup_loop
        self._task = asyncio.create_task(session_idle_cleanup_loop())
        logger.info("lifecycle.started service=%s", self.name)

    async def stop(self) -> None:
        if hasattr(self, "_task") and self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass


class _CacheRefreshService(LifecycleService):
    name = "cache_refresh"

    async def start(self) -> None:
        import asyncio
        from swx_core.background_task import refresh_translation_cache
        self._task = asyncio.create_task(refresh_translation_cache())
        logger.info("lifecycle.started service=%s", self.name)

    async def stop(self) -> None:
        if hasattr(self, "_task") and self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass