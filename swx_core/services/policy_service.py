"""
Policy Service
--------------
Business logic for Policy management.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from swx_core.models.policy import Policy
from swx_core.repositories import policy_repository
from swx_core.services.policy.policy_registry import PolicyRegistry


async def list_policies_service(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Policy]:
    """List all policies (database only)."""
    return await policy_repository.list_policies(session, skip, limit)


async def list_system_policies_service() -> List[dict]:
    """List all system policies (from registry)."""
    return PolicyRegistry.list_all()


async def get_policy_service(
    session: AsyncSession, policy_id: str
) -> Policy:
    """Get a policy by ID (checks both database and system policies)."""
    # Check database first
    db_policy = await policy_repository.get_policy_by_id(session, policy_id)
    if db_policy:
        return db_policy
    
    # Check system policies
    system_policy = PolicyRegistry.get(policy_id)
    if system_policy:
        # Convert dict to Policy object for response
        # Note: System policies are read-only
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System policies cannot be retrieved as Policy objects. Use /system endpoint."
        )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Policy '{policy_id}' not found"
    )


async def create_policy_service(
    session: AsyncSession, policy: Policy
) -> Policy:
    """Create a new policy."""
    # Check if policy_id already exists in database
    if await policy_repository.policy_exists(session, policy.policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Policy with ID '{policy.policy_id}' already exists"
        )
    
    # Check if it conflicts with a system policy
    if PolicyRegistry.get(policy.policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Policy ID '{policy.policy_id}' conflicts with a system policy"
        )
    
    return await policy_repository.create_policy(session, policy)


async def update_policy_service(
    session: AsyncSession, policy_id: str, policy_data: dict
) -> Policy:
    """Update a policy."""
    # Check if it's a system policy
    if PolicyRegistry.get(policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update system policies"
        )
    
    policy = await policy_repository.update_policy(session, policy_id, policy_data)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found"
        )
    
    return policy


async def delete_policy_service(
    session: AsyncSession, policy_id: str
) -> None:
    """Delete a policy (cannot delete system policies)."""
    # Check if it's a system policy
    if PolicyRegistry.get(policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system policies"
        )
    
    deleted = await policy_repository.delete_policy(session, policy_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found"
        )
