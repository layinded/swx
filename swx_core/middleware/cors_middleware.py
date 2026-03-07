"""
CORS Middleware Setup
---------------------
This module configures CORS (Cross-Origin Resource Sharing) for the FastAPI application.

Features:
- Allows cross-origin requests from specified origins.
- Supports credentials, methods, and headers configuration.

Functions:
- `setup_cors_middleware(app)`: Applies CORS settings to the FastAPI app.
"""

from starlette.middleware.cors import CORSMiddleware
from swx_core.config.settings import settings


def setup_cors_middleware(app):
    """
    Configures CORS for the FastAPI application.

    Args:
        app: The FastAPI application instance.

    Behavior:
        - Uses allowed origins from `settings.all_cors_origins`.
        - Defaults to allowing all origins (`*`) if no specific origins are set.
        - Enables credentials, all HTTP methods, and all headers.
    """
    allowed_origins = settings.all_cors_origins if settings.all_cors_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
