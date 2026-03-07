"""
Policy Dependencies
------------------
FastAPI dependencies for policy enforcement.
"""

from typing import Optional, Annotated, Callable
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database.db import SessionDep
from swx_core.services.policy.policy_engine import PolicyEngine, PolicyDecision
from swx_core.services.policy.actor import Actor, ActorType
from swx_core.services.policy.resource import Resource
from swx_core.services.policy.context import PolicyContext
from swx_core.auth.user.dependencies import UserDep
from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.rbac.helpers import get_user_permissions, get_user_roles
from swx_core.services.audit_logger import get_audit_logger, ActorType as AuditActorType, AuditOutcome
from swx_core.services.policy.actor import ActorType as PolicyActorType
from swx_core.services.settings_service import get_settings_service
from swx_core.config.settings import settings as env_settings
from swx_core.middleware.logging_middleware import logger
from datetime import datetime


async def build_actor_from_user(
    session: AsyncSession,
    user: UserDep,
    team_id: Optional[UUID] = None
) -> Actor:
    """Build Actor from User."""
    # Get roles and permissions
    roles = await get_user_roles(session, user.id, team_id=team_id, domain="user")
    permissions = await get_user_permissions(session, user.id, team_id=team_id, domain="user")
    
    # Get billing entitlements
    from swx_core.services.billing.entitlement_resolver import EntitlementResolver
    from swx_core.models.billing import BillingAccountType
    from swx_core.services.billing.feature_registry import FeatureRegistry
    
    entitlements = []
    subscription_status = None
    
    resolver = EntitlementResolver(session)
    if team_id:
        # Team billing
        account_type = BillingAccountType.TEAM
        owner_id = team_id
    else:
        # User billing
        account_type = BillingAccountType.USER
        owner_id = user.id
    
    # Check all registered features
    for feature_def in FeatureRegistry.list_all():
        has_access = await resolver.has(owner_id, account_type, feature_def.key)
        if has_access:
            entitlements.append(feature_def.key)
    
    # Get subscription status (simplified - would need to query subscription)
    # For now, if user has any entitlements, assume active
    subscription_status = "active" if entitlements else "none"
    
    return Actor(
        id=user.id,
        type=PolicyActorType.USER,
        roles=[r.name for r in roles],
        permissions=[p.name for p in permissions],
        team_id=team_id,
        is_superuser=user.is_superuser,
        attributes={
            "email": user.email,
            "is_active": user.is_active,
            "subscription_status": subscription_status,
            "entitlements": entitlements,
        }
    )


async def build_actor_from_admin(
    session: AsyncSession,
    admin: AdminUserDep
) -> Actor:
    """Build Actor from AdminUser."""
    # Admin users have admin domain roles/permissions
    roles = await get_user_roles(session, admin.id, domain="admin")
    permissions = await get_user_permissions(session, admin.id, domain="admin")
    
    return Actor(
        id=admin.id,
        type=PolicyActorType.ADMIN,
        roles=[r.name for r in roles],
        permissions=[p.name for p in permissions],
        is_superuser=admin.is_superuser,
        attributes={
            "email": admin.email,
            "is_active": admin.is_active,
        }
    )


def require_policy(
    action: str,
    resource_type: str,
    resource_id: Optional[UUID] = None,
    resource_owner_id: Optional[UUID] = None,
    resource_team_id: Optional[UUID] = None,
    resource_attributes: Optional[dict] = None,
):
    """
    FastAPI dependency to enforce policy evaluation.
    
    Usage:
        @router.put("/teams/{team_id}")
        async def update_team(
            team_id: UUID,
            current_user: UserDep,
            session: SessionDep,
            request: Request,
            _policy: None = Depends(require_policy(
                action="team:update",
                resource_type="team",
                resource_id=team_id
            ))
        ):
            # Policy already evaluated - proceed
            ...
    
    Args:
        action: Action being attempted (e.g., "team:update")
        resource_type: Type of resource (e.g., "team")
        resource_id: Resource ID (if accessing specific resource)
        resource_owner_id: Resource owner ID (if known)
        resource_team_id: Resource team ID (if known)
        resource_attributes: Additional resource attributes
    """
    async def policy_checker(
        session: SessionDep = None,
        request: Request = None,
        current_user: Optional[UserDep] = None,
        current_admin: Optional[AdminUserDep] = None,
    ) -> None:
        # Determine actor - check admin first, then user
        actor = None
        if current_admin:
            actor = await build_actor_from_admin(session, current_admin)
        elif current_user:
            # Try to get team_id from request if available
            team_id = resource_team_id  # Could also extract from request
            actor = await build_actor_from_user(session, current_user, team_id=team_id)
        
        if not actor:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Build resource
        resource = Resource(
            type=resource_type,
            id=resource_id,
            owner_id=resource_owner_id,
            team_id=resource_team_id,
            attributes=resource_attributes or {}
        )
        
        # Get environment from settings (with fallback to env var)
        settings_service = get_settings_service(session)
        environment = await settings_service.get_string(
            "system.environment",
            default=env_settings.ENVIRONMENT or "local"
        )
        
        # Build context
        context = PolicyContext(
            timestamp=datetime.utcnow(),
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            environment=environment,
            request_id=request.headers.get("x-request-id", "") if request else ""
        )
        
        # Evaluate policy
        engine = PolicyEngine(session)
        result = await engine.evaluate(actor, action, resource, context)
        
        # Audit log - every policy evaluation is logged
        audit = get_audit_logger(session)
        await audit.log_event(
            action=f"policy.evaluate.{action}",
            actor_type=AuditActorType.USER if current_user else AuditActorType.ADMIN,
            actor_id=str(actor.id),
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            outcome=AuditOutcome.SUCCESS if result.decision == PolicyDecision.ALLOW else AuditOutcome.FAILURE,
            context={
                "policy_result": result.to_dict(),
                "action": action,
                "resource_type": resource_type,
                "actor_type": actor.type.value,
                "actor_roles": actor.roles,
                "actor_permissions": actor.permissions,
            },
            request=request
        )
        
        # Check decision
        if result.decision == PolicyDecision.DENY:
            logger.warning(
                f"Policy DENIED: actor={actor.id}, action={action}, "
                f"resource={resource_id}, reason={result.reason}"
            )
            
            # Optionally trigger alert for sensitive actions
            if action.startswith(("admin:", "billing:", "user:delete")):
                from swx_core.services.alert_engine import alert_engine
                from swx_core.services.channels.models import AlertSeverity, AlertSource
                await alert_engine.emit(
                    severity=AlertSeverity.WARNING,
                    source=AlertSource.POLICY,
                    event_type="POLICY_DENIAL",
                    message=f"Policy denied {action} for actor {actor.id}",
                    metadata={
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": str(resource_id) if resource_id else None,
                        "reason": result.reason,
                    }
                )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {result.reason}"
            )
        
        # Policy passed - continue
        logger.debug(
            f"Policy ALLOWED: actor={actor.id}, action={action}, resource={resource_id}"
        )
    
    return Depends(policy_checker)
