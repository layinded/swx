from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.permission import Permission, PermissionCreate, PermissionUpdate

async def get_permission_by_id(session: AsyncSession, permission_id: UUID) -> Optional[Permission]:
    return await session.get(Permission, permission_id)

async def get_permission_by_name(session: AsyncSession, name: str) -> Optional[Permission]:
    statement = select(Permission).where(Permission.name == name)
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def get_all_permissions(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Permission]:
    statement = select(Permission).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())

async def create_permission(session: AsyncSession, permission_in: PermissionCreate) -> Permission:
    db_obj = Permission.model_validate(permission_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def update_permission(session: AsyncSession, db_obj: Permission, permission_in: PermissionUpdate) -> Permission:
    update_data = permission_in.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def delete_permission(session: AsyncSession, db_obj: Permission) -> None:
    await session.delete(db_obj)
    await session.commit()
