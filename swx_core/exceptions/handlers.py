"""
SwX Exception Handlers
-----------------------
Reusable FastAPI exception handlers with production-safe responses.

Call ``register_exception_handlers(app)`` during bootstrap to install all
four handlers.  Each handler logs with structured context (request_id,
correlation_id, path, method) and ensures production 500 responses never
leak internal exception details.
"""

from __future__ import annotations

import logging
import traceback
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from swx_core.utils.errors import SwXError

logger = logging.getLogger("SwX-API")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request_id(request: Request) -> str:
    """Extract request_id from request state (set by AuditMiddleware)."""
    state = request.state
    return getattr(state, "request_id", None) or "unknown"


def _correlation_id(request: Request) -> Optional[str]:
    """Extract correlation_id from X-Correlation-ID header or request state."""
    header = request.headers.get("x-correlation-id")
    if header:
        return header
    return getattr(request.state, "correlation_id", None)


def _is_production(request: Request) -> bool:
    """Best-effort check whether we are in a production environment."""
    env = getattr(request.app.state, "environment", None)
    if env:
        return env in ("production", "prod")
    # Fall back to settings if app.state.environment is not set.
    try:
        from swx_core.config.settings import settings

        return settings.ENVIRONMENT in ("production", "prod")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def swx_error_handler(request: Request, exc: SwXError) -> JSONResponse:
    """Handle SwXError subclasses — structured JSON response."""
    correlation_id = _correlation_id(request)
    log_extra: dict = {
        "request_id": _request_id(request),
        "path": request.url.path,
        "method": request.method,
        "error_code": exc.code,
    }
    if correlation_id:
        log_extra["correlation_id"] = correlation_id

    logger.warning(
        "SwXError: [%s] %s path=%s request_id=%s",
        exc.code,
        exc.message,
        request.url.path,
        log_extra["request_id"],
        extra=log_extra,
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    """Handle RequestValidationError — 422 with sanitized details."""
    request_id = _request_id(request)
    correlation_id = _correlation_id(request)

    logger.warning(
        "Validation error at %s: %s request_id=%s",
        request.url.path,
        exc.errors(),
        request_id,
        extra={"request_id": request_id, "correlation_id": correlation_id, "path": request.url.path},
    )

    # Sanitize body — non-serializable types (UploadFile, bytes, FormData)
    # are replaced with None to avoid serialization errors.
    safe_body: object = None
    if hasattr(exc, "body"):
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

    from swx_core.utils.json import dumps as swx_dumps

    try:
        serialized = swx_dumps({"detail": safe_detail, "body": safe_body})
        return Response(content=serialized, status_code=422, media_type="application/json")
    except Exception:
        logger.exception("Failed to serialize validation error response")
        minimal = [
            {"type": e.get("type"), "msg": e.get("msg"), "loc": e.get("loc")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": minimal, "body": None})


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions."""
    request_id = _request_id(request)
    logger.error(
        "HTTP %s at %s: %s request_id=%s",
        exc.status_code,
        request.url.path,
        exc.detail,
        request_id,
        extra={"request_id": request_id, "path": request.url.path, "status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions — production-safe 500 response."""
    request_id = _request_id(request)
    correlation_id = _correlation_id(request)
    is_prod = _is_production(request)

    log_extra: dict = {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
    }
    if correlation_id:
        log_extra["correlation_id"] = correlation_id

    logger.critical(
        "Unhandled exception at %s: %s request_id=%s",
        request.url.path,
        type(exc).__name__,
        request_id,
        extra=log_extra,
        exc_info=True,
    )

    # In production, never leak internal details.
    if is_prod:
        content: dict = {"error": "Internal Server Error", "request_id": request_id}
        if correlation_id:
            content["correlation_id"] = correlation_id
    else:
        content = {
            "error": "Internal Server Error",
            "request_id": request_id,
            "detail": str(exc),
            "type": type(exc).__name__,
        }
        if correlation_id:
            content["correlation_id"] = correlation_id

    return JSONResponse(status_code=500, content=content)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register all four standard SWX exception handlers on *app*.

    Handlers are installed in specificity order: most specific first so
    FastAPI matches the correct handler for each exception type.
    """
    app.add_exception_handler(SwXError, swx_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    logger.info("exception_handlers.registered handlers=4")