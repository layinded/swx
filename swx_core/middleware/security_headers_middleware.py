# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Pure-ASGI security headers middleware with SSE awareness.

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.

SOC 2 CC7.1: Adds X-Request-ID for request correlation, CSP-Report-Only
for violation reporting, and a settings toggle for enabling/disabling
all security headers.
"""

import os
import uuid
from dataclasses import dataclass, field

from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass
class SecurityHeadersConfig:
    hsts_max_age: int = 63072000
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    content_type_nosniff: bool = True
    frame_options: str = "DENY"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = "geolocation=(), microphone=(), camera=()"
    xss_protection: str = "0"
    corp_for_sse: str = "cross-origin"
    corp_default: str = "same-origin"
    csp_api: str = "default-src 'none'; frame-ancestors 'none'"
    csp_report_only: str = "default-src 'none'; frame-ancestors 'none'; report-uri /api/utils/csp-report"
    enabled: bool = True
    request_id_header: str = "X-Request-ID"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "local").lower())


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that adds security headers without buffering.

    Unlike BaseHTTPMiddleware, this streams the response through without
    consuming the body, which is essential for SSE endpoints.
    """

    def __init__(self, app: ASGIApp, config: SecurityHeadersConfig | None = None) -> None:
        self.app: ASGIApp = app
        self.config: SecurityHeadersConfig = config or SecurityHeadersConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self.config.enabled:
            await self.app(scope, receive, send)
            return

        original_send = send
        injected = False

        async def send_with_headers(message: Message) -> None:
            nonlocal injected
            if message["type"] == "http.response.start" and not injected:
                message = _inject_headers(message, self.config, scope)
                injected = True
            await original_send(message)

        await self.app(scope, receive, send_with_headers)


def _inject_headers(message: Message, config: SecurityHeadersConfig, scope: Scope) -> Message:
    """Return a copy of the response-start message with security headers injected.

    Preserves duplicate header entries (e.g. multiple Set-Cookie) by keeping
    the original list and only appending new headers that don't already exist.
    """
    existing: list[tuple[bytes, bytes]] = list(message.get("headers", []))
    existing_keys = {k.lower() for k, _ in existing}

    # X-Request-ID for request correlation (SOC 2 CC7.1)
    request_id_header = config.request_id_header.lower().encode()
    if request_id_header not in existing_keys:
        request_id = str(uuid.uuid4())
        existing.append((request_id_header, request_id.encode()))
        scope.setdefault("state", {})[config.request_id_header.lower()] = request_id

    if config.content_type_nosniff and b"x-content-type-options" not in existing_keys:
        existing.append((b"x-content-type-options", b"nosniff"))
    if b"x-frame-options" not in existing_keys:
        existing.append((b"x-frame-options", config.frame_options.encode()))
    if b"x-xss-protection" not in existing_keys:
        existing.append((b"x-xss-protection", config.xss_protection.encode()))
    if b"referrer-policy" not in existing_keys:
        existing.append((b"referrer-policy", config.referrer_policy.encode()))
    if b"permissions-policy" not in existing_keys:
        existing.append((b"permissions-policy", config.permissions_policy.encode()))

    content_type = b""
    for k, v in existing:
        if k.lower() == b"content-type":
            content_type = v
            break
    is_sse = content_type.startswith(b"text/event-stream")
    if b"cross-origin-resource-policy" not in existing_keys:
        corp = config.corp_for_sse.encode() if is_sse else config.corp_default.encode()
        existing.append((b"cross-origin-resource-policy", corp))

    if b"cross-origin-opener-policy" not in existing_keys:
        existing.append((b"cross-origin-opener-policy", b"same-origin"))
    if b"cross-origin-embedder-policy" not in existing_keys:
        existing.append((b"cross-origin-embedder-policy", b"require-corp"))

    path = scope.get("path", "/")
    if not _is_docs_path(path) and b"content-security-policy" not in existing_keys:
        existing.append((b"content-security-policy", config.csp_api.encode()))

    # CSP-Report-Only for violation reporting (SOC 2 CC7.1)
    if config.csp_report_only and b"content-security-policy-report-only" not in existing_keys:
        existing.append((b"content-security-policy-report-only", config.csp_report_only.encode()))

    if config.environment == "production":
        if b"strict-transport-security" not in existing_keys:
            parts = [f"max-age={config.hsts_max_age}"]
            if config.hsts_include_subdomains:
                parts.append("includeSubDomains")
            if config.hsts_preload:
                parts.append("preload")
            existing.append((b"strict-transport-security", "; ".join(parts).encode()))

    return {"type": message["type"], "headers": existing, "status": message.get("status", 200)}


def _is_docs_path(path: str) -> bool:
    return path.rstrip("/") in ("/docs", "/redoc", "/openapi.json")


def setup_security_headers(app: ASGIApp, config: SecurityHeadersConfig | None = None) -> None:
    """Register security headers middleware on a FastAPI application.

    Uses pure ASGI middleware instead of BaseHTTPMiddleware to preserve
    SSE streaming compatibility.
    """
    from fastapi import FastAPI
    if isinstance(app, FastAPI):
        app.add_middleware(SecurityHeadersMiddleware, config=config)
    else:
        raise TypeError(f"Expected FastAPI app, got {type(app).__name__}")


def apply_middleware(app: ASGIApp) -> None:
    """Apply security headers middleware via the dynamic middleware loader."""
    from swx_core.config.settings import settings
    config = SecurityHeadersConfig(enabled=settings.SECURITY_HEADERS_ENABLED)
    setup_security_headers(app, config)