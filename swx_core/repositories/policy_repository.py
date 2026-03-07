"""
Policy Repository
-----------------
Database operations for Policy model.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.policy import Policy


async def get_policy_by_id(
    session: AsyncSession, policy_id: str
) -> Optional[Policy]:
    """Get a policy by its policy_id."""
    stmt = select(Policy).where(Policy.policy_id == policy_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_policies(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Policy]:
    """List all policies with pagination."""
    stmt = select(Policy).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_policy(session: AsyncSession, policy: Policy) -> Policy:
    """Create a new policy."""
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


async def update_policy(
    session: AsyncSession, policy_id: str, policy_data: dict
) -> Optional[Policy]:
    """Update a policy."""
    policy = await get_policy_by_id(session, policy_id)
    if not policy:
        return None
    
    for key, value in policy_data.items():
        if hasattr(policy, key):
            setattr(policy, key, value)
    
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


async def delete_policy(session: AsyncSession, policy_id: str) -> bool:
    """Delete a policy."""
    policy = await get_policy_by_id(session, policy_id)
    if not policy:
        return False
    
    await session.delete(policy)
    await session.commit()
    return True


async def policy_exists(session: AsyncSession, policy_id: str) -> bool:
    """Check if a policy exists."""
    policy = await get_policy_by_id(session, policy_id)
    return policy is not None
