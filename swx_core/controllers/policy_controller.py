"""
Policy Controller
----------------
Controller layer for Policy management operations.
"""

from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.policy import Policy
from swx_core.services import policy_service


async def list_policies_controller(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Policy]:
    """List all database policies."""
    return await policy_service.list_policies_service(session, skip, limit)


async def list_system_policies_controller() -> List[dict]:
    """List all system policies."""
    return await policy_service.list_system_policies_service()


async def get_policy_controller(
    session: AsyncSession, policy_id: str
) -> Policy:
    """Get a policy by ID."""
    return await policy_service.get_policy_service(session, policy_id)


async def create_policy_controller(
    session: AsyncSession, policy: Policy
) -> Policy:
    """Create a new policy."""
    return await policy_service.create_policy_service(session, policy)


async def update_policy_controller(
    session: AsyncSession, policy_id: str, policy_data: dict
) -> Policy:
    """Update a policy."""
    return await policy_service.update_policy_service(session, policy_id, policy_data)


async def delete_policy_controller(
    session: AsyncSession, policy_id: str
) -> None:
    """Delete a policy."""
    return await policy_service.delete_policy_service(session, policy_id)
