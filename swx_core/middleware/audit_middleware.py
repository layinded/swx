# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Audit Logging Middleware — pure ASGI, SSE-safe.

Ensures every request has a unique Request ID and injects it into response
headers.  Sets request_id on scope["state"] for downstream consumers.

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.
"""

import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastapi import FastAPI


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    """Extract a header value by lowercase name match."""
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


class AuditMiddleware:
    """Pure-ASGI audit middleware — assigns request IDs, SSE-safe."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_list: list[tuple[bytes, bytes]] = scope.get("headers", [])
        request_id = _extract_header(headers_list, b"x-request-id") or str(uuid.uuid4())

        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
        else:
            setattr(state, "request_id", request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def apply_middleware(app: FastAPI) -> None:
    """Apply the AuditMiddleware to a FastAPI application."""
    app.add_middleware(AuditMiddleware)