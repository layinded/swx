import asyncio
from swx_core.database.db import AsyncSessionLocal
from swx_core.models.admin_user import AdminUser
from swx_core.security.password_security import get_password_hash
from sqlmodel import select

async def reset():
    async with AsyncSessionLocal() as session:
        admin = (await session.execute(select(AdminUser))).scalar_one_or_none()
        if admin:
            admin.hashed_password = await get_password_hash('securepassword')
            session.add(admin)
            await session.commit()
            print('Password reset done')

if __name__ == "__main__":
    asyncio.run(reset())
