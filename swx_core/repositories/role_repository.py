from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.role import Role, RoleCreate, RoleUpdate

async def get_role_by_id(session: AsyncSession, role_id: UUID) -> Optional[Role]:
    return await session.get(Role, role_id)

async def get_role_by_name(session: AsyncSession, name: str) -> Optional[Role]:
    statement = select(Role).where(Role.name == name)
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def get_all_roles(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Role]:
    statement = select(Role).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())

async def create_role(session: AsyncSession, role_in: RoleCreate) -> Role:
    db_obj = Role.model_validate(role_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def update_role(session: AsyncSession, db_obj: Role, role_in: RoleUpdate) -> Role:
    update_data = role_in.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def delete_role(session: AsyncSession, db_obj: Role) -> None:
    await session.delete(db_obj)
    await session.commit()
