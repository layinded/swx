from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from swx_core.utils.health import HealthChecker

router = APIRouter(prefix="/utils")


def _get_checker(request: Request) -> HealthChecker | None:
    return getattr(request.app.state, "health_checker", None)


@router.get("/health-check", tags=["Health"])
async def health_check():
    """Liveness probe — returns 200 if the process is alive."""
    return {"status": "healthy", "service": "swx-api"}


@router.get("/health", tags=["Health"])
async def health_detailed(request: Request):
    """Detailed health check using HealthChecker for all registered services."""
    checker = _get_checker(request)
    if checker is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "message": "health_checker not initialized"},
        )

    result = await checker.check_all()
    status_code = 503 if result.status == "unhealthy" else 200
    return JSONResponse(status_code=status_code, content=result.model_dump())


@router.get("/ready", tags=["Health"])
async def readiness_check(request: Request):
    """Readiness probe — 200 only when all *required* services are healthy.

    Kubernetes uses this to decide whether to route traffic to this pod.
    Returns 503 with details if any required service is unhealthy.
    """
    checker = _get_checker(request)
    if checker is None:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "message": "health_checker not initialized"},
        )

    result = await checker.check_all()

    required_unhealthy = [
        name
        for name in checker.required_services
        if name in result.services and result.services[name].status == "unhealthy"
    ]

    if required_unhealthy:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "unhealthy_required": required_unhealthy,
                "services": {k: v.model_dump() for k, v in result.services.items()},
            },
        )

    return {"status": "ready", "service": "swx-api"}