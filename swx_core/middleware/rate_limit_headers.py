# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Rate limit response headers middleware.

Reads rate limit state from `request.state` (set by the rate limiter)
and attaches standard X-RateLimit-* headers to the response.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RateLimitHeadersMiddleware:
    """Pure ASGI middleware that adds X-RateLimit-* headers from request.state."""

    def __init__(self, app: ASGIApp) -> None:
        self.app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.get("state")
        injected = False
        original_send = send

        async def send_with_headers(message: Message) -> None:
            nonlocal injected
            if message["type"] == "http.response.start" and not injected:
                headers = list(message.get("headers", []))
                if state is not None:
                    for attr, header in (
                        ("rate_limit_limit", b"X-RateLimit-Limit"),
                        ("rate_limit_remaining", b"X-RateLimit-Remaining"),
                        ("rate_limit_reset", b"X-RateLimit-Reset"),
                    ):
                        value = getattr(state, attr, None)
                        if value is not None:
                            headers.append((header, str(value).encode()))
                message = {**message, "headers": headers}
                injected = True
            await original_send(message)

        await self.app(scope, receive, send_with_headers)


def apply_middleware(app: ASGIApp) -> None:
    """Register rate limit headers middleware on a FastAPI application."""
    from fastapi import FastAPI
    if isinstance(app, FastAPI):
        app.add_middleware(RateLimitHeadersMiddleware)
    else:
        raise TypeError(f"Expected FastAPI app, got {type(app).__name__}")