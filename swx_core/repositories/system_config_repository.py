from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import and_

from swx_core.models.system_config import SystemConfig, SettingCategory


async def get_active_rate_limit_configs(
    session: AsyncSession,
) -> List[SystemConfig]:
    stmt = select(SystemConfig).where(
        and_(
            SystemConfig.category == SettingCategory.RATE_LIMIT,  # pyright: ignore[reportArgumentType]
            SystemConfig.is_active.is_(True),  # pyright: ignore[reportAttributeAccessIssue]
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
