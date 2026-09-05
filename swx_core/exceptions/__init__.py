"""
SwX Exception Handling
-----------------------
Reusable exception handlers for FastAPI applications.

Instead of registering handlers ad-hoc in ``main.py``, applications call
``register_exception_handlers(app)`` once during bootstrap.  The handlers
are:

- ``SwXError`` → structured JSON with ``{success, error: {code, message, details}}``
- ``RequestValidationError`` → 422 with sanitized error detail
- ``StarletteHTTPException`` → ``{error: detail}`` with status code
- ``Exception`` → generic 500 (never leaks internal details in production)

Usage::

    from swx_core.exceptions import register_exception_handlers

    app = FastAPI(...)
    register_exception_handlers(app)
"""

from swx_core.utils.errors import SwXError  # noqa: F401 — re-export for convenience