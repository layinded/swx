"""
RBAC FastAPI Dependencies
-------------------------
This module provides FastAPI dependencies for enforcing permissions and roles.

These dependencies can be used in route decorators to enforce access control.
"""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Request, status

from swx_core.database.db import SessionDep
from swx_core.models.user import User
from swx_core.rbac.helpers import (
    has_permission,
    has_role,
    check_team_permission,
)
from swx_core.auth.user.dependencies import UserDep
from swx_core.utils.language_helper import translate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType


def require_permission(
    permission: str,
    team_id: Optional[UUID] = None,
    domain: Optional[str] = None,
):
    """
    Factory function that creates a FastAPI dependency to require a specific permission.

    Example:
        ```python
        @router.get("/users", dependencies=[Depends(require_permission("user:read"))])
        def list_users():
            ...
        ```

    Args:
        permission: The permission name (e.g., "user:read", "article:delete").
        team_id: Optional team ID for team-scoped permission check.
        domain: Optional domain filter ("admin", "user", "system").

    Returns:
        A FastAPI dependency function that validates the permission.
    """

    async def permission_checker(
        session: SessionDep,
        current_user: UserDep,
        request: Request,
    ) -> User:
        """
        Checks if the current user has the required permission.

        Args:
            session: Database session.
            current_user: The authenticated user.
            request: FastAPI request object.

        Returns:
            The authenticated user if they have the permission.

        Raises:
            HTTPException (403): If the user lacks the required permission.
        """
        if not await has_permission(session, current_user, permission, team_id=team_id):
            await alert_engine.emit(
                severity=AlertSeverity.WARNING,
                source=AlertSource.RBAC,
                event_type="PERMISSION_DENIED",
                message=f"User {current_user.email} denied permission: {permission}",
                actor_type=AlertActorType.USER,
                actor_id=str(current_user.id),
                resource_type="permission",
                resource_id=permission,
                metadata={"path": request.url.path, "team_id": str(team_id) if team_id else None}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate(
                    request, "user_lacks_required_permission"
                ) or f"Permission required: {permission}",
            )
        return current_user

    return permission_checker


def require_role(
    role: str,
    team_id: Optional[UUID] = None,
    domain: Optional[str] = None,
):
    """
    Factory function that creates a FastAPI dependency to require a specific role.

    Example:
        ```python
        @router.get("/admin", dependencies=[Depends(require_role("admin", domain="admin"))])
        def admin_dashboard():
            ...
        ```

    Args:
        role: The role name (e.g., "admin", "editor").
        team_id: Optional team ID for team-scoped role check.
        domain: Optional domain filter ("admin", "user", "system").

    Returns:
        A FastAPI dependency function that validates the role.
    """

    async def role_checker(
        session: SessionDep,
        current_user: UserDep,
        request: Request,
    ) -> User:
        """
        Checks if the current user has the required role.

        Args:
            session: Database session.
            current_user: The authenticated user.
            request: FastAPI request object.

        Returns:
            The authenticated user if they have the role.

        Raises:
            HTTPException (403): If the user lacks the required role.
        """
        if not await has_role(session, current_user, role, team_id=team_id, domain=domain):
            await alert_engine.emit(
                severity=AlertSeverity.WARNING,
                source=AlertSource.RBAC,
                event_type="ROLE_DENIED",
                message=f"User {current_user.email} denied role: {role}",
                actor_type=AlertActorType.USER,
                actor_id=str(current_user.id),
                resource_type="role",
                resource_id=role,
                metadata={"path": request.url.path, "team_id": str(team_id) if team_id else None, "domain": domain}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate(
                    request, "user_lacks_required_role"
                ) or f"Role required: {role}",
            )
        return current_user

    return role_checker


def require_team_permission(
    team_id: UUID,
    permission: str,
):
    """
    Factory function that creates a FastAPI dependency to require a permission in a team.

    Example:
        ```python
        @router.get("/teams/{team_id}/members", dependencies=[Depends(require_team_permission(team_id, "team:read"))])
        def list_team_members(team_id: UUID):
            ...
        ```

    Args:
        team_id: The team ID.
        permission: The permission name.

    Returns:
        A FastAPI dependency function that validates the team permission.
    """

    async def team_permission_checker(
        session: SessionDep,
        current_user: UserDep,
        request: Request,
    ) -> User:
        """
        Checks if the current user has the required permission in the team.

        Args:
            session: Database session.
            current_user: The authenticated user.
            request: FastAPI request object.

        Returns:
            The authenticated user if they have the permission.

        Raises:
            HTTPException (403): If the user lacks the required team permission.
        """
        if not await check_team_permission(session, current_user, team_id, permission):
            await alert_engine.emit(
                severity=AlertSeverity.WARNING,
                source=AlertSource.RBAC,
                event_type="TEAM_PERMISSION_DENIED",
                message=f"User {current_user.email} denied team permission: {permission}",
                actor_type=AlertActorType.USER,
                actor_id=str(current_user.id),
                resource_type="team_permission",
                resource_id=permission,
                metadata={"path": request.url.path, "team_id": str(team_id)}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate(
                    request, "user_lacks_required_team_permission"
                ) or f"Team permission required: {permission}",
            )
        return current_user

    return team_permission_checker


# Type aliases for common permission dependencies
RequirePermission = Annotated[User, Depends(require_permission)]
RequireRole = Annotated[User, Depends(require_role)]
RequireTeamPermission = Annotated[User, Depends(require_team_permission)]
