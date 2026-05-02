"""
Audit Logging Middleware
-------------------------
This middleware captures request-level context for audit logging,
such as Request ID and IP address.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure every request has a unique Request ID
    and to capture basic request context.
    """

    async def dispatch(self, request: Request, call_next):
        # Assign a unique Request ID if not already present
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        
        # Return Request ID in response headers for tracing
        response.headers["X-Request-ID"] = request_id
        return response


def apply_middleware(app: FastAPI):
    """
    Applies the AuditMiddleware to the FastAPI application.
    """
    app.add_middleware(AuditMiddleware)
