# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
API Configuration Settings Mixin.

Defines API-level configuration: project identity, route prefixes, API
versions, host URLs, environment, and logging configuration.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ApiSettingsMixin(BaseSettings):
    """API, routing, host, environment, and logging configuration."""

    # API Configuration
    PROJECT_NAME: str = "SwX API"
    ROUTE_PREFIX: str = Field("/api", description="Base API route prefix")
    CORE_ROUTE_PREFIX: str = Field(
        "",
        description=(
            "Prefix for core framework routes. Empty string puts core routes at /api/auth. "
            "Set to '/v1' to mount core routes at /api/v1/auth for consistency with app versioned routes."
        ),
    )
    API_VERSIONS: list[str] = Field(["v1", "v2"], description="Supported API versions")
    DEFAULT_API_VERSION: str = Field("v1", description="Default API version")
    STRICT_ROUTE_LOADING: bool = Field(
        False,
        description="If True, raise errors for missing routers instead of warnings",
    )

    BACKEND_HOST: str = Field(
        "http://localhost:8000", description="Backend API host URL"
    )
    FRONTEND_HOST: str = Field(
        "http://localhost:5173", description="Frontend application URL"
    )
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    LOG_LEVEL: Literal[
        "debug", "info", "warning", "error", "critical", "production"
    ] = Field(default="warning")

    LOG_DIR: str = Field(
        default="logs",
        description="Directory for log files (default: 'logs')"
    )

    LOG_FORMAT: Literal["json", "text"] = Field(
        default="json",
        description="Log output format: 'json' for structured JSON (production), 'text' for human-readable (development)",
    )

    @field_validator("LOG_LEVEL", mode="before")
    def normalize_log_level(cls, v: object) -> object:
        """Normalize LOG_LEVEL to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v
