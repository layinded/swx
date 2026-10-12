"""
Sentry Middleware
-----------------
This module initializes Sentry for error monitoring in production environments.

Features:
- Captures unhandled exceptions.
- Provides error tracking and logging with Sentry.
- Validates DSN format before initialization.
- Gracefully degrades if Sentry SDK is unavailable or DSN is invalid.

Functions:
- `setup_sentry_middleware()`: Configures Sentry SDK.
- `apply_middleware(app)`: Called by dynamic middleware loader.
"""

import logging

from swx_core.config.settings import settings
from swx_core.config.validation import is_valid_dsn

logger = logging.getLogger(__name__)


def setup_sentry_middleware():
    if not settings.MONITORING_ENABLED:
        return
    sentry_dsn = getattr(settings, "SENTRY_DSN", None)
    if not sentry_dsn:
        return
    if not is_valid_dsn(str(sentry_dsn)):
        logger.warning("Sentry DSN is invalid or contains a placeholder — skipping initialization")
        return
    if settings.ENVIRONMENT == "local":
        return

    try:
        import sentry_sdk
    except ImportError:
        return

    try:
        sentry_sdk.init(dsn=str(sentry_dsn), enable_tracing=True)
        logger.info("Sentry SDK initialized successfully")
    except Exception:
        logger.exception("Failed to initialize Sentry SDK — monitoring disabled")


def apply_middleware(app):
    """
    Apply Sentry middleware (called by dynamic middleware loader).

    Sentry doesn't use FastAPI middleware - it hooks into Python directly.

    Args:
        app: The FastAPI application instance (unused, kept for interface consistency).
    """
    setup_sentry_middleware()
