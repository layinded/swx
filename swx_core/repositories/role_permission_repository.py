from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.role_permission import RolePermission

async def get_role_permission(session: AsyncSession, role_id: UUID, permission_id: UUID) -> Optional[RolePermission]:
    statement = select(RolePermission).where(
        RolePermission.role_id == role_id,
        RolePermission.permission_id == permission_id
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def assign_permission_to_role(session: AsyncSession, role_id: UUID, permission_id: UUID) -> RolePermission:
    db_obj = RolePermission(role_id=role_id, permission_id=permission_id)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def remove_permission_from_role(session: AsyncSession, db_obj: RolePermission) -> None:
    await session.delete(db_obj)
    await session.commit()

async def list_role_permissions(session: AsyncSession, role_id: UUID) -> List[RolePermission]:
    statement = select(RolePermission).where(RolePermission.role_id == role_id)
    result = await session.execute(statement)
    return list(result.scalars().all())
