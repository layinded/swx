"""
Policy Management Routes
------------------------
Admin-only APIs for managing policies.
"""

from typing import List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, status, Request

from swx_core.database.db import SessionDep
from swx_core.models.policy import Policy
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import policy_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/policy",
    tags=["admin-policy"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/", response_model=List[Policy])
async def list_policies(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all database policies."""
    return await policy_controller.list_policies_controller(session, skip, limit)


@router.get("/system", response_model=List[dict])
async def list_system_policies() -> Any:
    """List all system policies (defined in code)."""
    return await policy_controller.list_system_policies_controller()


@router.get("/{policy_id}", response_model=Policy)
async def get_policy(
    policy_id: str,
    session: SessionDep,
    current_admin: AdminUserDep,
) -> Any:
    """Get a policy by ID."""
    return await policy_controller.get_policy_controller(session, policy_id)


@router.post("/", response_model=Policy, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: Policy,
    session: SessionDep,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Create a new policy."""
    audit = get_audit_logger(session)
    try:
        result = await policy_controller.create_policy_controller(session, policy)
        await audit.log_event(
            action="policy.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy.policy_id,
            outcome=AuditOutcome.SUCCESS,
            context={"policy_id": policy.policy_id},
            request=request
        )
        return result
    except Exception as e:
        await audit.log_event(
            action="policy.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy.policy_id,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), "policy_id": policy.policy_id},
            request=request
        )
        raise


@router.patch("/{policy_id}", response_model=Policy)
async def update_policy(
    policy_id: str,
    policy_update: dict,
    session: SessionDep,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Update a policy."""
    audit = get_audit_logger(session)
    try:
        result = await policy_controller.update_policy_controller(
            session, policy_id, policy_update
        )
        await audit.log_event(
            action="policy.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy_id,
            outcome=AuditOutcome.SUCCESS,
            context=policy_update,
            request=request
        )
        return result
    except Exception as e:
        await audit.log_event(
            action="policy.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy_id,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **policy_update},
            request=request
        )
        raise


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    session: SessionDep,
    current_admin: AdminUserDep,
    request: Request,
) -> None:
    """Delete a policy (cannot delete system policies)."""
    audit = get_audit_logger(session)
    try:
        await policy_controller.delete_policy_controller(session, policy_id)
        await audit.log_event(
            action="policy.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy_id,
            outcome=AuditOutcome.SUCCESS,
            context={},
            request=request
        )
    except Exception as e:
        await audit.log_event(
            action="policy.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="policy",
            resource_id=policy_id,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise
