"""
Sentry Middleware
-----------------
This module initializes Sentry for error monitoring in production environments.

Features:
- Captures unhandled exceptions.
- Provides error tracking and logging with Sentry.

Functions:
- `setup_sentry_middleware()`: Configures Sentry SDK.
- `apply_middleware(app)`: Called by dynamic middleware loader.
"""

from swx_core.config.settings import settings


def setup_sentry_middleware():
    """
    Initializes Sentry for error monitoring.

    Behavior:
        - Only enabled if `settings.SENTRY_DSN` is set.
        - Disabled in local development environments.
    """
    if not getattr(settings, "SENTRY_DSN", None):
        return
    if settings.ENVIRONMENT == "local":
        return

    try:
        import sentry_sdk
    except ImportError:
        return

    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


def apply_middleware(app):
    """
    Apply Sentry middleware (called by dynamic middleware loader).
    
    This function is called automatically by swx_core.utils.loader.load_middleware().
    Sentry doesn't use FastAPI middleware - it hooks into Python directly.
    
    Args:
        app: The FastAPI application instance (unused, kept for interface consistency).
    """
    setup_sentry_middleware()