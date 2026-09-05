"""
SwX Application Bootstrap
---------------------------
Deterministic startup/shutdown lifecycle with stage logging and timing.

The bootstrap process follows a fixed sequence of stages, each logged with
structured timing data.  Circular provider dependencies are detected and
reported clearly.  Applications use ``bootstrap_app()`` to initialise the
container, providers, and routes; ``create_swx_app()`` to create the full
FastAPI application with lifespan management.

Usage (thin application entry point)::

    from swx_core import create_swx_app, bootstrap_app

    app = create_swx_app(title="My App", app_name="my_app")
    container = bootstrap_app(app)

Usage (manual control)::

    from swx_core.bootstrap import bootstrap_app

    app = FastAPI(...)
    container = bootstrap_app(app, providers=[...])
"""

from __future__ import annotations

import time
from enum import Enum
from typing import List, Optional, Type

from swx_core.config.discovery import discovery
from swx_core.container.container import Container, get_container
from swx_core.middleware.logging_middleware import logger
from swx_core.providers.base import ServiceProvider
from swx_core.router import router as core_router


# ---------------------------------------------------------------------------
# Bootstrap stages — deterministic, logged, timed
# ---------------------------------------------------------------------------


class BootstrapStage(str, Enum):
    """Ordered stages of the bootstrap process."""

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
    """Timings and metadata produced by ``bootstrap_app()``."""

    def __init__(self, container: Container) -> None:
        self.container = container
        self.stage_timings: dict[str, float] = {}
        self.stage_errors: dict[str, Exception] = {}
        self.provider_names: list[str] = []

    @property
    def success(self) -> bool:
        return not self.stage_errors


# ---------------------------------------------------------------------------
# Circular dependency detection
# ---------------------------------------------------------------------------


class CircularProviderError(Exception):
    """Raised when circular provider dependencies are detected."""

    def __init__(self, chain: list[str], cycle_start: str) -> None:
        self.chain = chain
        self.cycle_start = cycle_start
        cycle = " -> ".join(chain + [cycle_start])
        super().__init__(f"Circular provider dependency detected: {cycle}")


def _validate_provider_dependencies(
    provider_classes: list[Type[ServiceProvider]],
) -> None:
    """Check declared ``depends`` lists for cycles.

    ``ServiceProvider.depends`` is a list of provider class names that must
    register before this provider.  This function validates that the
    dependency graph has no cycles using a simple DFS cycle detection.
    """
    name_map: dict[str, Type[ServiceProvider]] = {}
    for cls in provider_classes:
        name_map[cls.__name__] = cls

    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(name: str, path: list[str]) -> None:
        if name in stack:
            raise CircularProviderError(path, name)
        if name in visited:
            return
        visited.add(name)
        stack.add(name)
        cls = name_map.get(name)
        if cls and hasattr(cls, "depends"):
            for dep in cls.depends:
                dfs(dep, path + [name])
        stack.discard(name)

    for cls in provider_classes:
        dfs(cls.__name__, [])


# ---------------------------------------------------------------------------
# Core providers (in registration order)
# ---------------------------------------------------------------------------

CORE_PROVIDERS = [
    "swx_core.providers.database_provider.DatabaseServiceProvider",
    "swx_core.providers.event_provider.EventServiceProvider",
    "swx_core.providers.auth_provider.AuthServiceProvider",
    "swx_core.providers.rate_limit_provider.RateLimitServiceProvider",
    "swx_core.providers.event_bridge_provider.EventBridgeServiceProvider",
    "swx_core.providers.billing_provider.BillingServiceProvider",
]


def _load_provider_class(class_path: str) -> Type[ServiceProvider]:
    """Dynamically load a provider class from its full module path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _discover_user_providers() -> List[str]:
    """Discover user-defined providers in ``app/providers/``."""
    import pkgutil

    providers: list[str] = []
    providers_path = discovery.app_providers_path

    if not providers_path.exists():
        logger.debug("App providers directory not found: %s", providers_path)
        return providers

    for finder, name, is_pkg in pkgutil.iter_modules([str(providers_path)]):
        if name.endswith("_provider") or name == "app_provider":
            module_path = f"{discovery.app_providers_module}.{name}"
            try:
                module = __import__(module_path, fromlist=[name])
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ServiceProvider)
                        and attr is not ServiceProvider
                    ):
                        providers.append(f"{module_path}.{attr_name}")
            except Exception as e:
                logger.warning("Failed to load provider %s: %s", module_path, e)

    return providers


def _extract_route_paths(router_obj: object) -> set[str]:
    """Extract all path strings from a router or app, handling _IncludedRouter."""
    paths: set[str] = set()
    for route in getattr(router_obj, "routes", []):
        if hasattr(route, "path"):
            paths.add(route.path)
        elif hasattr(route, "original_router"):
            paths.update(_extract_route_paths(route.original_router))
    return paths


# ---------------------------------------------------------------------------
# Stage logging helper
# ---------------------------------------------------------------------------


def _log_stage(stage: BootstrapStage, elapsed: float, extra: dict | None = None) -> None:
    """Emit a structured log record for a completed bootstrap stage."""
    log_extra: dict = {
        "bootstrap_stage": stage.value,
        "duration_ms": round(elapsed * 1000, 2),
    }
    if extra:
        log_extra.update(extra)
    logger.info(
        "bootstrap.%s elapsed=%.2fs",
        stage.value,
        elapsed,
        extra=log_extra,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def bootstrap_app(
    app=None,
    providers: Optional[List[str]] = None,
    discover_user_providers: bool = True,
    register_middleware: bool = True,
) -> Container:
    """Bootstrap the application with all service providers.

    This is the main entry point for initialising the SwX framework.
    Each stage is logged with timing data for observability.

    Args:
        app: FastAPI application instance (optional).
        providers: Additional provider class paths to register.
        discover_user_providers: Whether to auto-discover user providers.
        register_middleware: Whether to apply the canonical middleware
            stack.  Pass ``False`` when middleware is already applied
            (e.g. by ``create_swx_app()``).  Defaults to ``True`` so
            that standalone ``bootstrap_app()`` calls get middleware.

    Returns:
        Configured container instance.
    """
    result = BootstrapResult(get_container())
    total_start = time.monotonic()

    # ---- Stage: Container initialisation --------------------------------
    stage_start = time.monotonic()
    container = result.container
    if app is not None:
        app.state.container = container
    _log_stage(BootstrapStage.CONTAINER_INITIALIZATION, time.monotonic() - stage_start)

    # ---- Stage: Route discovery (register core routes) ------------------
    stage_start = time.monotonic()
    if app is not None:
        existing_route_paths = _extract_route_paths(app)
        if core_router.routes:
            core_paths = _extract_route_paths(core_router)
            if not core_paths.issubset(existing_route_paths):
                app.include_router(core_router)
                logger.info("Registered core routes with app")
            else:
                logger.info("Core routes already registered, skipping duplicate registration")
    _log_stage(BootstrapStage.ROUTE_DISCOVERY, time.monotonic() - stage_start)

    # ---- Stage: Provider registration ------------------------------------
    stage_start = time.monotonic()
    all_providers = CORE_PROVIDERS[:]
    if discover_user_providers and discovery.app_exists():
        user_providers = _discover_user_providers()
        all_providers.extend(user_providers)
    if providers:
        all_providers.extend(providers)

    provider_classes: list[Type[ServiceProvider]] = []
    for provider_path in all_providers:
        try:
            provider_classes.append(_load_provider_class(provider_path))
        except Exception as e:
            logger.warning("Failed to load provider %s: %s", provider_path, e)

    provider_classes.sort(key=lambda p: getattr(p, "priority", 100))

    # Validate dependency graph before registration.
    try:
        _validate_provider_dependencies(provider_classes)
    except CircularProviderError as exc:
        logger.critical("bootstrap.circular_dependency %s", exc)
        raise

    provider_instances: list[ServiceProvider] = []
    for provider_class in provider_classes:
        try:
            provider = provider_class(container)
            provider_instances.append(provider)
        except Exception as e:
            logger.error("Failed to instantiate provider %s: %s", provider_class.__name__, e)

    for provider in provider_instances:
        name = provider.__class__.__name__
        try:
            provider.register()
            logger.debug("Registered: %s", name)
        except Exception as e:
            logger.error("Failed to register %s: %s", name, e)

    result.provider_names = [p.__class__.__name__ for p in provider_instances]
    _log_stage(
        BootstrapStage.PROVIDER_REGISTRATION,
        time.monotonic() - stage_start,
        extra={"providers": result.provider_names},
    )

    # ---- Stage: Provider boot -------------------------------------------
    stage_start = time.monotonic()
    for provider in provider_instances:
        name = provider.__class__.__name__
        try:
            provider.boot()
            logger.info("Booted: %s", name)
        except Exception as e:
            logger.error("Failed to boot %s: %s", name, e)
            result.stage_errors[f"provider_boot.{name}"] = e
    _log_stage(BootstrapStage.PROVIDER_BOOT, time.monotonic() - stage_start)

    # ---- Stage: Middleware setup -----------------------------------------
    stage_start = time.monotonic()
    if register_middleware and app is not None:
        from swx_core.middleware.stack import apply_middleware_stack
        apply_middleware_stack(app)
        logger.info("Applied canonical middleware stack")
    elif not register_middleware:
        logger.debug("Middleware setup skipped (register_middleware=False)")
    elif app is None:
        logger.warning("Middleware setup skipped (no app instance)")
    _log_stage(BootstrapStage.MIDDLEWARE_SETUP, time.monotonic() - stage_start)

    # ---- Stage: Default hooks -------------------------------------------
    _register_default_hooks()

    # ---- Stage: Event listeners -----------------------------------------
    app_exists = discovery.app_exists()
    has_listeners = discovery.has_listeners()

    if app_exists and has_listeners:
        logger.info("Registering event listeners...")
        try:
            register_event_listeners(container)
        except Exception as e:
            logger.error("Failed to register event listeners: %s", e)

    # ---- Stage: Application ready ---------------------------------------
    total_elapsed = time.monotonic() - total_start
    _log_stage(
        BootstrapStage.APPLICATION_READY,
        total_elapsed,
        extra={
            "providers_count": len(provider_instances),
            "success": not result.stage_errors,
        },
    )
    result.stage_timings[BootstrapStage.APPLICATION_READY.value] = total_elapsed
    logger.info(
        "Application bootstrapped with %d providers in %.2fs",
        len(provider_instances),
        total_elapsed,
    )

    return container


def bootstrap(*args, **kwargs) -> Container:
    """Alias for ``bootstrap_app()``."""
    return bootstrap_app(*args, **kwargs)


def register_webhook_routes(app) -> None:
    """Register webhook routes with the FastAPI app."""
    from swx_core.webhooks.flutterwave_webhook import (
        router as flutterwave_webhook_router,
    )
    from swx_core.webhooks.paystack_webhook import router as paystack_webhook_router
    from swx_core.webhooks.stripe_webhook import router as stripe_webhook_router

    app.include_router(stripe_webhook_router)
    app.include_router(paystack_webhook_router)
    app.include_router(flutterwave_webhook_router)
    logger.info("Registered webhook routes")


def register_event_listeners(container: Container) -> None:
    """Register user event listeners from ``app/listeners/``."""
    import pkgutil

    from swx_core.events.dispatcher import event_bus
    from swx_core.events.listener import Listener

    listeners_path = discovery.app_listeners_path

    if not listeners_path.exists():
        logger.debug("App listeners directory not found: %s", listeners_path)
        return

    for finder, name, is_pkg in pkgutil.iter_modules([str(listeners_path)]):
        try:
            module = __import__(
                f"{discovery.app_listeners_module}.{name}", fromlist=[name]
            )
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Listener)
                    and attr is not Listener
                ):
                    listener_instance = attr()
                    event_bus.listen(
                        listener_instance.event,
                        listener_instance.handle,
                        priority=getattr(listener_instance, "priority", 50),
                        queueable=getattr(listener_instance, "queueable", False),
                    )
                    logger.info(
                        "Registered listener: %s -> '%s' (priority=%s, queueable=%s)",
                        attr_name,
                        listener_instance.event,
                        getattr(listener_instance, "priority", 50),
                        getattr(listener_instance, "queueable", False),
                    )
        except Exception as e:
            logger.error("Failed to load listener %s: %s", name, e, exc_info=True)


def get_registered_services() -> dict:
    """Return all registered services in the container."""
    container = get_container()
    return {name: binding.binding_type.value for name, binding in container.get_bindings().items()}


def resolve(name: str):
    """Convenience function to resolve a service from the container."""
    return get_container().make(name)


def diagnose_discovery() -> dict:
    """Diagnose discovery configuration for debugging."""
    return {
        "app_name": discovery.app_name,
        "app_base": str(discovery.app_base),
        "app_exists": discovery.app_exists(),
        "listeners_path": str(discovery.app_listeners_path),
        "has_listeners": discovery.has_listeners(),
        "phase_3_will_run": discovery.app_exists() and discovery.has_listeners(),
    }


def _register_default_hooks() -> None:
    from swx_core.config.settings import settings
    from swx_core.core.default_hooks import (
        assign_default_role,
        create_billing_account,
        create_personal_team,
    )
    from swx_core.core.hooks import registration_hooks

    if settings.AUTO_ASSIGN_DEFAULT_ROLE:
        registration_hooks.add_post_register(assign_default_role)
        logger.info("Default registration hook: assign role '%s'", settings.DEFAULT_USER_ROLE)

    if settings.AUTO_CREATE_BILLING_ACCOUNT and settings.BILLING_ENABLED:
        registration_hooks.add_post_register(create_billing_account)
        logger.info("Default registration hook: create billing account")

    if getattr(settings, "AUTO_CREATE_PERSONAL_TEAM", True):
        registration_hooks.add_post_register(create_personal_team)
        logger.info("Default registration hook: create personal team")