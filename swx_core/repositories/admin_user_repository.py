from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.admin_user import AdminUser
from swx_core.security.password_security import verify_password


async def get_admin_by_email(*, session: AsyncSession, email: str) -> AdminUser | None:
    statement = select(AdminUser).where(AdminUser.email == email)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def authenticate_admin(*, session: AsyncSession, email: str, password: str) -> AdminUser | None:
    admin_user = await get_admin_by_email(session=session, email=email)
    if not admin_user or not admin_user.hashed_password:
        return None
    if not await verify_password(password, admin_user.hashed_password):
        return None
    return admin_user
