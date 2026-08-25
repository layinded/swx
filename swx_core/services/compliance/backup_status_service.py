"""Backup status service for SOC 2 CC6.5 backup verification."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger


async def get_backup_status(session: AsyncSession) -> dict[str, object]:
    backup_url = settings.BACKUP_STATUS_URL  # pyright: ignore[reportAttributeAccessIssue]
    if backup_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(backup_url)
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except (ValueError, TypeError):
                        logger.warning("Backup status endpoint returned non-JSON body.")
                    else:
                        return {
                            "source": "external",
                            "status": "available",
                            "data": payload,
                        }
        except httpx.HTTPError as exc:
            logger.warning("Backup status check failed: %s", exc)

    return {
        "source": "placeholder",
        "status": "not_configured",
        "last_backup_timestamp": None,
        "backup_size_bytes": None,
        "verification_status": "pending",
        "message": "Configure BACKUP_STATUS_URL to enable live backup status checks.",
    }