import json
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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
    """JSON log formatter with SOC 2 CC7.2 structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        for attr in (
            "request_id", "user_id", "ip", "path", "method",
            "status_code", "duration_ms", "file", "line",
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
        for attr in ("request_id", "user_id", "ip", "method", "path", "status_code", "duration_ms"):
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


class LoggingMiddleware(BaseHTTPMiddleware):
    """SOC 2 CC7.2 structured logging middleware.

    Captures request_id, user_id, ip, method, path, status_code,
    and duration_ms for every HTTP request.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start_time = time.time()

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
        user_id = getattr(request.state, "user_id", None) if hasattr(request.state, "user_id") else None
        ip = request.client.host if request.client else None

        log_data: dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        if request_id:
            log_data["request_id"] = request_id
        if user_id:
            log_data["user_id"] = str(user_id)
        if ip:
            log_data["ip"] = ip

        level = logging.CRITICAL
        if response.status_code < 400:
            level = logging.INFO
        elif response.status_code < 500:
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

        response.headers["X-Request-ID"] = request_id or ""
        return response