from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.user_role import UserRole, UserRoleCreate

async def get_user_role_by_id(session: AsyncSession, user_role_id: UUID) -> Optional[UserRole]:
    return await session.get(UserRole, user_role_id)

async def get_user_role_assignment(session: AsyncSession, assignment: UserRoleCreate) -> Optional[UserRole]:
    statement = select(UserRole).where(
        UserRole.user_id == assignment.user_id,
        UserRole.role_id == assignment.role_id,
        UserRole.team_id == assignment.team_id,
        UserRole.resource_id == assignment.resource_id
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def assign_role_to_user(session: AsyncSession, assignment: UserRoleCreate) -> UserRole:
    db_obj = UserRole.model_validate(assignment)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def remove_role_from_user(session: AsyncSession, db_obj: UserRole) -> None:
    await session.delete(db_obj)
    await session.commit()

async def list_user_roles(session: AsyncSession, user_id: UUID) -> List[UserRole]:
    statement = select(UserRole).where(UserRole.user_id == user_id)
    result = await session.execute(statement)
    return list(result.scalars().all())
