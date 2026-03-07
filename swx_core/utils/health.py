"""
Health Check Utilities
----------------------
Advanced health check endpoints and monitoring.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from pydantic import BaseModel, Field

from swx_core.database.db_setup import get_session


class HealthStatus(BaseModel):
    """Health status for a single service."""
    name: str
    status: str = Field(description="healthy, unhealthy, or degraded")
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class HealthCheckResult(BaseModel):
    """Overall health check result."""
    status: str = Field(description="healthy, unhealthy, or degraded")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    uptime_seconds: float = Field(description="Application uptime in seconds")
    services: Dict[str, HealthStatus] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthChecker:
    """
    Health checker for monitoring services.
    
    Usage:
        health_checker = HealthChecker()
        health_checker.add_check("database", check_database)
        health_checker.add_check("redis", check_redis)
        
        @router.get("/health")
        async def health():
            return await health_checker.check_all()
    """
    
    def __init__(self, version: str = "1.0.0"):
        """
        Initialize health checker.
        
        Args:
            version: Application version
        """
        self.version = version
        self._start_time = datetime.utcnow()
        self._checks: Dict[str, Callable] = {}
        self._required_services: List[str] = []
    
    def add_check(
        self,
        name: str,
        check_func: Callable,
        required: bool = True,
    ) -> None:
        """
        Add a health check function.
        
        Args:
            name: Service name
            check_func: Async function that returns HealthStatus
            required: Whether this service is required for overall health
        """
        self._checks[name] = check_func
        if required:
            self._required_services.append(name)
    
    async def check_service(self, name: str) -> HealthStatus:
        """
        Run a single health check.
        
        Args:
            name: Service name
            
        Returns:
            HealthStatus for the service
        """
        check_func = self._checks.get(name)
        
        if not check_func:
            return HealthStatus(
                name=name,
                status="unknown",
                message=f"No health check registered for {name}",
            )
        
        try:
            start_time = datetime.utcnow()
            result = await check_func()
            end_time = datetime.utcnow()
            
            if result.latency_ms is None:
                result.latency_ms = (end_time - start_time).total_seconds() * 1000
            
            return result
        
        except Exception as e:
            return HealthStatus(
                name=name,
                status="unhealthy",
                message=str(e),
            )
    
    async def check_all(self) -> HealthCheckResult:
        """
        Run all health checks.
        
        Returns:
            HealthCheckResult with all service statuses
        """
        results = {}
        
        # Run all checks in parallel
        tasks = [self.check_service(name) for name in self._checks]
        statuses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, status in zip(self._checks.keys(), statuses):
            if isinstance(status, Exception):
                results[name] = HealthStatus(
                    name=name,
                    status="unhealthy",
                    message=str(status),
                )
            else:
                results[name] = status
        
        # Determine overall status
        overall_status = self._determine_overall_status(results)
        
        return HealthCheckResult(
            status=overall_status,
            version=self.version,
            uptime_seconds=(datetime.utcnow() - self._start_time).total_seconds(),
            services=results,
        )
    
    def _determine_overall_status(self, results: Dict[str, HealthStatus]) -> str:
        """Determine overall health status."""
        # If any required service is unhealthy, overall is unhealthy
        for name in self._required_services:
            if name in results and results[name].status == "unhealthy":
                return "unhealthy"
        
        # If any service is unhealthy, overall is degraded
        for status in results.values():
            if status.status == "unhealthy":
                return "degraded"
        
        # If any service is degraded, overall is degraded
        for status in results.values():
            if status.status == "degraded":
                return "degraded"
        
        return "healthy"


# Pre-defined health check functions

async def check_database() -> HealthStatus:
    """Check database connectivity."""
    try:
        async with get_session() as session:
            await session.execute("SELECT 1")
        
        return HealthStatus(
            name="database",
            status="healthy",
            message="Database connection successful",
        )
    
    except Exception as e:
        return HealthStatus(
            name="database",
            status="unhealthy",
            message=f"Database connection failed: {str(e)}",
        )


async def check_redis(redis_url: str = "redis://localhost:6379") -> HealthStatus:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(redis_url)
        start_time = datetime.utcnow()
        
        await client.ping()
        
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        await client.close()
        
        return HealthStatus(
            name="redis",
            status="healthy",
            message="Redis connection successful",
            latency_ms=latency,
        )
    
    except ImportError:
        return HealthStatus(
            name="redis",
            status="degraded",
            message="Redis client not installed",
        )
    
    except Exception as e:
        return HealthStatus(
            name="redis",
            status="unhealthy",
            message=f"Redis connection failed: {str(e)}",
        )


async def check_celery(celery_app=None) -> HealthStatus:
    """Check Celery worker availability."""
    try:
        if celery_app is None:
            from swx_core.config.settings import settings
            celery_app = getattr(settings, "celery_app", None)
        
        if celery_app is None:
            return HealthStatus(
                name="celery",
                status="degraded",
                message="Celery not configured",
            )
        
        # Check active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            return HealthStatus(
                name="celery",
                status="healthy",
                message=f"Celery workers available: {len(active_workers)}",
                details={"workers": list(active_workers.keys())},
            )
        
        return HealthStatus(
            name="celery",
            status="degraded",
            message="No active Celery workers",
        )
    
    except Exception as e:
        return HealthStatus(
            name="celery",
            status="unhealthy",
            message=f"Celery check failed: {str(e)}",
        )


async def check_external_service(
    name: str,
    url: str,
    timeout: float = 5.0,
) -> HealthStatus:
    """
    Check external service health.
    
    Args:
        name: Service name
        url: Health check URL
        timeout: Timeout in seconds
        
    Returns:
        HealthStatus for the service
    """
    try:
        import httpx
        
        start_time = datetime.utcnow()
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
        
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        if response.status_code < 400:
            return HealthStatus(
                name=name,
                status="healthy",
                message=f"{name} is responding",
                latency_ms=latency,
            )
        
        return HealthStatus(
            name=name,
            status="degraded",
            message=f"{name} returned status {response.status_code}",
            latency_ms=latency,
        )
    
    except asyncio.TimeoutError:
        return HealthStatus(
            name=name,
            status="unhealthy",
            message=f"{name} health check timed out",
        )
    
    except Exception as e:
        return HealthStatus(
            name=name,
            status="unhealthy",
            message=f"{name} health check failed: {str(e)}",
        )


# Default health checker instance
_default_health_checker: Optional[HealthChecker] = None


def get_health_checker(version: str = None) -> HealthChecker:
    """Get or create default health checker."""
    global _default_health_checker
    
    if _default_health_checker is None:
        if version is None:
            try:
                from swx_core import __version__
                version = __version__
            except ImportError:
                version = "unknown"
        
        _default_health_checker = HealthChecker(version=version)
        
        # Add default checks
        _default_health_checker.add_check("database", check_database)
        _default_health_checker.add_check("redis", check_redis)
    
    return _default_health_checker


def setup_health_checker(
    version: str,
    checks: Dict[str, Callable] = None,
    required_services: List[str] = None,
) -> HealthChecker:
    """
    Set up health checker with custom checks.
    
    Args:
        version: Application version
        checks: Dictionary of health check functions
        required_services: List of required service names
        
    Returns:
        Configured HealthChecker
    """
    checker = HealthChecker(version=version)
    
    # Add default checks
    checker.add_check("database", check_database)
    checker.add_check("redis", check_redis, required=False)
    
    # Add custom checks
    if checks:
        for name, check_func in checks.items():
            required = name in (required_services or [])
            checker.add_check(name, check_func, required=required)
    
    return checker