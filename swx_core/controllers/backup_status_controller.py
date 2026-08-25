"""Backup status controller for SOC 2 CC6.5 backup verification."""

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.compliance.backup_status_service import get_backup_status


async def get_backup_status_controller(session: AsyncSession) -> dict[str, object]:
    return await get_backup_status(session)