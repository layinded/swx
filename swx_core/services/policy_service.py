"""
Policy Service
--------------
Business logic for Policy management.

Events Emitted:
- policy.created: Emitted when a new policy is created
- policy.updated: Emitted when a policy is updated
- policy.deleted: Emitted when a policy is deleted
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from swx_core.models.policy import Policy
from swx_core.repositories import policy_repository
from swx_core.services.policy.policy_registry import PolicyRegistry
from swx_core.events.dispatcher import EventBus, Event


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
    session: AsyncSession, 
    policy: Policy,
    event_context: Dict[str, Any] | None = None,
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
    
    created_policy = await policy_repository.create_policy(session, policy)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="policy.created",
        payload={
            "id": str(created_policy.id),
            "data": {"policy_id": policy.policy_id, "name": policy.name},
            **({"context": event_context} if event_context else {}),
        },
    ))
    
    return created_policy


async def update_policy_service(
    session: AsyncSession, 
    policy_id: str, 
    policy_data: dict,
    event_context: Dict[str, Any] | None = None,
) -> Policy:
    """Update a policy."""
    # Check if it's a system policy
    if PolicyRegistry.get(policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update system policies"
        )
    
    old_policy = await policy_repository.get_policy_by_id(session, policy_id)
    old_values = {"name": old_policy.name, "description": old_policy.description} if old_policy else {}
    
    policy = await policy_repository.update_policy(session, policy_id, policy_data)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found"
        )
    
    new_values = {"name": policy.name, "description": policy.description}
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="policy.updated",
        payload={
            "id": str(policy.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context else {}),
        },
    ))
    
    return policy


async def delete_policy_service(
    session: AsyncSession, 
    policy_id: str,
    event_context: Dict[str, Any] | None = None,
) -> None:
    """Delete a policy (cannot delete system policies)."""
    # Check if it's a system policy
    if PolicyRegistry.get(policy_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system policies"
        )
    
    policy = await policy_repository.get_policy_by_id(session, policy_id)
    policy_name = policy.name if policy else policy_id
    
    deleted = await policy_repository.delete_policy(session, policy_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found"
        )
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="policy.deleted",
        payload={
            "id": policy_id,
            "data": {"name": policy_name},
            **({"context": event_context} if event_context else {}),
        },
    ))
