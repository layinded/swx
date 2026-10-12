"""
SwX Middleware Stack
---------------------
Ordered middleware configuration with documented security implications.

FastAPI applies middleware in LIFO order (last added = outermost = first
executed).  This module defines the canonical ordering and provides
``apply_middleware_stack()`` to register them in the correct sequence so
that the *logical* outer-to-inner order matches security best practices.

Usage::

    from swx_core.middleware.stack import apply_middleware_stack

    app = FastAPI(...)
    apply_middleware_stack(app)

Applications can customise the stack by passing ``overrides`` or by
setting individual middleware ``enabled=False``.

Caveat: Starlette session middleware (``SessionMiddleware``) must be
added separately via ``setup_session_middleware(app)`` because it uses
a different API.  It is called inside ``apply_middleware_stack`` by
default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import FastAPI

from swx_core.middleware.logging_middleware import logger


# ---------------------------------------------------------------------------
# Apply functions — MUST be defined before CANONICAL_ORDER references them.
# All use lazy imports to avoid circular dependencies.
# ---------------------------------------------------------------------------


def _apply_cors(app: FastAPI) -> None:
    from swx_core.middleware.cors_middleware import setup_cors_middleware
    setup_cors_middleware(app)


def _apply_security_headers(app: FastAPI) -> None:
    from swx_core.middleware.security_headers_middleware import apply_middleware
    apply_middleware(app)


def _apply_audit(app: FastAPI) -> None:
    from swx_core.middleware.audit_middleware import apply_middleware
    apply_middleware(app)


def _apply_logging(app: FastAPI) -> None:
    from swx_core.middleware.logging_middleware import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)


def _apply_rate_limit(app: FastAPI) -> None:
    from swx_core.middleware.rate_limit_middleware import apply_middleware
    apply_middleware(app)


def _apply_auth_rate_limit(app: FastAPI) -> None:
    from swx_core.middleware.auth_rate_limit import apply_middleware
    apply_middleware(app)


def _apply_rate_limit_headers(app: FastAPI) -> None:
    from swx_core.middleware.rate_limit_headers import apply_middleware
    apply_middleware(app)


def _apply_tenant(app: FastAPI) -> None:
    from swx_core.middleware.tenant_middleware import apply_middleware
    apply_middleware(app)


def _apply_csrf(app: FastAPI) -> None:
    from swx_core.middleware.csrf_middleware import apply_middleware
    apply_middleware(app)


def _apply_container(app: FastAPI) -> None:
    from swx_core.container.fastapi_integration import ContainerMiddleware
    app.add_middleware(ContainerMiddleware)


def _apply_session(app: FastAPI) -> None:
    from swx_core.middleware.session_middleware import setup_session_middleware
    setup_session_middleware(app)


def _apply_metrics(app: FastAPI) -> None:
    from swx_core.middleware.metrics_middleware import apply_middleware
    apply_middleware(app)


def _apply_region_routing(app: FastAPI) -> None:
    from swx_core.middleware.region_routing import apply_middleware
    apply_middleware(app)


@dataclass
class MiddlewareSpec:
    """Declarative description of a single middleware layer.

    Attributes:
        name: Human-readable identifier used in logs.
        apply_fn: Callable ``(app: FastAPI) -> None`` that adds the middleware.
        enabled: If ``False``, this layer is skipped entirely.
        required: If ``True``, a warning is logged when the layer is disabled.
        order: Logical execution order (lower = outer = first in, last out).
    """

    name: str
    apply_fn: Optional[Callable[[FastAPI], None]]
    enabled: bool = True
    required: bool = True
    order: int = 100


# ---------------------------------------------------------------------------
# Canonical middleware order (outermost → innermost)
# ---------------------------------------------------------------------------

CANONICAL_ORDER: list[MiddlewareSpec] = [
    MiddlewareSpec(name="cors", apply_fn=_apply_cors, order=10),
    MiddlewareSpec(name="security_headers", apply_fn=_apply_security_headers, order=20),
    MiddlewareSpec(name="audit", apply_fn=_apply_audit, order=30),
    MiddlewareSpec(name="logging", apply_fn=_apply_logging, order=40),
    MiddlewareSpec(name="rate_limit", apply_fn=_apply_rate_limit, order=50),
    MiddlewareSpec(name="auth_rate_limit", apply_fn=_apply_auth_rate_limit, order=60),
    MiddlewareSpec(name="rate_limit_headers", apply_fn=_apply_rate_limit_headers, order=70),
    MiddlewareSpec(name="tenant", apply_fn=_apply_tenant, order=80),
    MiddlewareSpec(name="csrf", apply_fn=_apply_csrf, required=False, order=90),
    MiddlewareSpec(name="container", apply_fn=_apply_container, required=False, order=100),
    MiddlewareSpec(name="session", apply_fn=_apply_session, order=110),
    MiddlewareSpec(name="metrics", apply_fn=_apply_metrics, enabled=False, required=False, order=120),
    MiddlewareSpec(name="region_routing", apply_fn=_apply_region_routing, enabled=False, required=False, order=130),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_middleware_stack(
    app: FastAPI,
    *,
    overrides: Optional[dict[str, bool]] = None,
) -> None:
    """Apply middleware in the canonical security order.

    The list is iterated **in reverse** because FastAPI is LIFO: the
    last middleware added is the outermost (first in, last out).

    Args:
        app: The FastAPI application.
        overrides: Dict mapping middleware name → enabled flag.
            Use this to enable/disable specific layers per application.
            Example: ``{"csrf": False, "metrics": True}``
    """
    overrides = overrides or {}

    # Build the effective list: apply overrides and filter enabled.
    specs: list[MiddlewareSpec] = []
    for spec in CANONICAL_ORDER:
        enabled = overrides.get(spec.name, spec.enabled)
        if not enabled:
            if spec.required:
                logger.warning(
                    "middleware.disabled name=%s (required layer disabled)", spec.name
                )
            else:
                logger.info("middleware.disabled name=%s", spec.name)
            continue
        specs.append(spec)

    # Sort by order (outermost first) then reverse for LIFO add-middleware.
    specs.sort(key=lambda s: s.order)

    # FastAPI LIFO: add innermost first so it ends up innermost.
    for spec in reversed(specs):
        if spec.apply_fn is None:
            logger.debug("middleware.skip name=%s (no apply_fn)", spec.name)
            continue
        try:
            spec.apply_fn(app)
            logger.info("middleware.applied name=%s order=%d", spec.name, spec.order)
        except Exception:
            logger.exception("middleware.failed name=%s", spec.name)