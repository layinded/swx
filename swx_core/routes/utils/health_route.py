"""
Health Check Routes
-------------------
This module defines health check endpoints for container orchestration and monitoring.

Features:
- Provides health check endpoint for Docker/Kubernetes healthchecks
- Database connectivity check
- Application status check

Routes:
- `GET /utils/health-check`: Basic health check (for Docker healthchecks)
- `GET /utils/health`: Detailed health check with database status
"""

from fastapi import APIRouter
from sqlmodel import text
from swx_core.database.db import SessionDep
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource

router = APIRouter(prefix="/utils")


@router.get("/health-check", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint for Docker/Kubernetes healthchecks.
    
    Returns:
        dict: Simple status response
    """
    return {"status": "healthy", "service": "swx-api"}


@router.get("/health", tags=["Health"])
async def health_detailed(session: SessionDep):
    """
    Detailed health check with database connectivity test.
    
    Args:
        session: Database session dependency (AsyncSession)
        
    Returns:
        dict: Detailed health status including database connectivity
    """
    db_status = "unknown"
    try:
        # Test database connectivity
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = "disconnected"
        await alert_engine.emit(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.INFRA,
            event_type="HEALTH_CHECK_DB_FAILURE",
            message=f"Database is down! Health check failed: {e}",
            metadata={"error": str(e)}
        )
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "swx-api",
        "database": db_status
    }
