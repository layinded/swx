# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""SOC 2 CC7.2 structured logging middleware — pure ASGI, SSE-safe.

Captures request_id, user_id, ip, method, path, status_code, and duration_ms
for every HTTP request.

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from swx_core.config.settings import settings

ENVIRONMENT = settings.ENVIRONMENT
LOG_LEVEL = settings.LOG_LEVEL
LOG_DIR = settings.LOG_DIR
LOG_FORMAT = settings.LOG_FORMAT

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("SwX-API")

LOG_LEVEL_MAPPING = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "production": logging.WARNING,
}

logger.setLevel(LOG_LEVEL_MAPPING.get(LOG_LEVEL, logging.WARNING))


class StructuredJSONFormatter(logging.Formatter):
    """JSON log formatter with SOC 2 CC7.2 structured fields.

    Always includes ``environment`` and ``service`` for operational
    correlation.  Additional fields (``correlation_id``,
    ``bootstrap_stage``, ``lifecycle_event``) are included when present
    on the log record.
    """

    # Static fields set once at import time.
    _environment: str = settings.ENVIRONMENT
    _service: str = settings.PROJECT_NAME

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "environment": self._environment,
            "service": self._service,
        }

        for attr in (
            "request_id", "correlation_id", "user_id", "ip", "path",
            "method", "status_code", "duration_ms", "file", "line",
            "bootstrap_stage", "lifecycle_event",
        ):
            value = getattr(record, attr, None)
            if value is not None:
                log_record[attr] = value

        if not any(k in log_record for k in ("file", "line")):
            log_record["file"] = record.filename
            log_record["line"] = record.lineno

        return json.dumps(log_record)


class TextFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:8} {record.getMessage()}"

        extras: list[str] = []
        for attr in (
            "request_id", "correlation_id", "user_id", "ip", "method",
            "path", "status_code", "duration_ms", "bootstrap_stage",
            "lifecycle_event",
        ):
            value = getattr(record, attr, None)
            if value is not None:
                extras.append(f"{attr}={value}")

        if extras:
            base += "  [" + " ".join(extras) + "]"

        return base


_formatter = StructuredJSONFormatter() if LOG_FORMAT == "json" else TextFormatter()

if ENVIRONMENT == "local":
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_formatter)
    logger.addHandler(console_handler)

log_filename = os.path.join(LOG_DIR, "swx_core.log")
file_handler = RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=10)
file_handler.setFormatter(_formatter)
logger.addHandler(file_handler)

logging.captureWarnings(True)


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    """Extract a header value by lowercase name match."""
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


def _get_state_attr(state: object, name: str) -> str | None:
    """Read an attribute from scope state, handling both dict and namespace objects."""
    if isinstance(state, dict):
        val = state.get(name)
        return str(val) if val is not None else None
    val = getattr(state, name, None)
    return str(val) if val is not None else None


class LoggingMiddleware:
    """SOC 2 CC7.2 structured logging middleware — pure ASGI, SSE-safe.

    Captures request_id, user_id, ip, method, path, status_code,
    and duration_ms for every HTTP request.

    Replaces the previous BaseHTTPMiddleware implementation which buffered
    response bodies and broke Server-Sent Events streaming.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        headers_list: list[tuple[bytes, bytes]] = scope.get("headers", [])
        request_id = _extract_header(headers_list, b"x-request-id") or str(uuid.uuid4())
        correlation_id = _extract_header(headers_list, b"x-correlation-id")

        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
            if correlation_id:
                state["correlation_id"] = correlation_id
        else:
            setattr(state, "request_id", request_id)
            if correlation_id:
                setattr(state, "correlation_id", correlation_id)

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        ip = client[0] if client else None

        async def send_with_logging(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                duration_ms = round((time.time() - start_time) * 1000, 2)

                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                if correlation_id:
                    headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                message = {**message, "headers": headers}

                log_data: dict[str, Any] = {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
                if request_id:
                    log_data["request_id"] = request_id
                if correlation_id:
                    log_data["correlation_id"] = correlation_id

                user_id = _get_state_attr(scope.get("state", {}), "user_id")
                if user_id:
                    log_data["user_id"] = user_id
                if ip:
                    log_data["ip"] = ip

                level = logging.CRITICAL
                if status_code < 400:
                    level = logging.INFO
                elif status_code < 500:
                    level = logging.WARNING

                if level >= logging.CRITICAL or ENVIRONMENT != "production":
                    record = logger.makeRecord(
                        name="SwX-API",
                        level=level,
                        fn="",
                        lno=0,
                        msg=json.dumps(log_data),
                        args=(),
                        exc_info=None,
                    )
                    for key, val in log_data.items():
                        setattr(record, key, val)
                    logger.handle(record)

            await send(message)

        await self.app(scope, receive, send_with_logging)