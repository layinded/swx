# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Region Routing Middleware
----------------------------
Pure-ASGI middleware that resolves a geographic region from the incoming
request (via a configurable header, defaulting to ``CF-IPCountry``) and
stores it on ``request.state.region`` for downstream consumption.

Opt-in: if no ``SWX_REGIONS`` mapping is configured, the middleware is a
no-op pass-through.

Configuration (via ``Settings`` or env vars):

- ``SWX_REGIONS``: JSON mapping of region code → list of country codes.
  Example: ``{"eu": ["DE","FR","NL"], "us": ["US","CA","MX"]}``
- ``SWX_REGION_HEADER``: Header carrying the country code
  (default: ``CF-IPCountry``).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


def _resolve_country(scope: Scope, header_name: str) -> str | None:
    """Extract the country code from request headers."""
    headers = scope.get("headers") or ()
    header_bytes = header_name.lower().encode("latin-1")
    for key, value in headers:
        if key == header_bytes:
            return value.decode("latin-1").strip().upper() or None
    return None


def resolve_region(country: str | None, regions: dict[str, list[str]]) -> str | None:
    """Map a country code to a region.

    Args:
        country: Two-letter country code (e.g. ``"DE"``, ``"US"``).
        regions: Mapping of region name → list of country codes.

    Returns:
        Region name string, or ``None`` if country is not in any region.
    """
    if not country:
        return None
    for region_name, countries in regions.items():
        if country in countries:
            return region_name
    return None


@dataclass
class RegionRoutingConfig:
    """Configuration for region routing middleware."""

    regions: dict[str, list[str]] = field(default_factory=dict)
    header_name: str = "CF-IPCountry"


class RegionRoutingMiddleware:
    """Pure-ASGI middleware that resolves request region from a header.

    Stores the resolved region on ``request.state.region`` (``str | None``).
    When no regions are configured, passes through without modification.
    """

    app: ASGIApp
    config: RegionRoutingConfig

    def __init__(self, app: ASGIApp, config: RegionRoutingConfig | None = None) -> None:
        self.app = app
        self.config = config or RegionRoutingConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # No-op when regions are not configured
        if not self.config.regions:
            await self.app(scope, receive, send)
            return

        country = _resolve_country(scope, self.config.header_name)
        region = resolve_region(country, self.config.regions)

        state = scope.setdefault("state", type("State", (), {})())
        setattr(state, "region", region)

        await self.app(scope, receive, send)


def _load_regions_from_env() -> dict[str, list[str]]:
    """Parse SWX_REGIONS from environment variable (JSON string)."""
    raw = os.getenv("SWX_REGIONS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            regions: dict[str, list[str]] = {}
            for k, v in parsed.items():
                if not isinstance(v, list):
                    logger.warning("SWX_REGIONS: skipping region '%s': expected list, got %s", k, type(v).__name__)
                    continue
                countries = [str(c) for c in v]
                regions[str(k)] = countries
            return regions
    except json.JSONDecodeError:
        logger.warning("SWX_REGIONS env var is not valid JSON, region routing disabled")
    return {}


def apply_middleware(app: ASGIApp) -> None:
    """Register region routing middleware on a FastAPI application."""
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        raise TypeError(f"Expected FastAPI app, got {type(app).__name__}")

    config = RegionRoutingConfig(
        regions=_load_regions_from_env(),
        header_name=os.getenv("SWX_REGION_HEADER", "CF-IPCountry"),
    )
    app.add_middleware(RegionRoutingMiddleware, config=config)