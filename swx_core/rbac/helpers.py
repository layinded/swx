"""
RBAC Helpers
------------
This module provides core permission and role checking functions.

Supports L1/L2 caching when USER_CACHE_ENABLED=True (backward compatible).
"""

from typing import Any, List, Optional, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.config.settings import settings
from swx_core.models.user import User
from swx_core.models.permission import Permission
from swx_core.models.role import Role
from swx_core.models.user_role import UserRole
from swx_core.models.role_permission import RolePermission
from swx_core.models.team_member import TeamMember
from swx_core.auth.auth_cache import user_auth_cache, get_cached_roles, set_cached_roles


async def get_user_roles(
    session: AsyncSession,
    user_id: UUID,
    team_id: Optional[UUID] = None,
    domain: Optional[str] = None,
) -> List[Role]:
    """Get all roles assigned to a user.

    When USER_CACHE_ENABLED=True, checks L1 → L2 → DB for roles.
    When disabled (default), queries DB directly (backward compatible).
    """
    user_id_str = str(user_id)

    if settings.USER_CACHE_ENABLED:
        cached = await get_cached_roles(user_id_str)
        if cached is not None:
            return [Role(**r) for r in cached]

    query = select(Role).join(UserRole).where(cast(Any, UserRole.user_id) == user_id)

    if team_id is not None:
        query = query.where(cast(Any, UserRole.team_id) == team_id)
    else:
        query = query.where(cast(Any, UserRole.team_id).is_(None))

    if domain is not None:
        query = query.where(cast(Any, Role.domain) == domain)

    result = await session.execute(query)
    roles = list(result.scalars().all())

    if settings.USER_CACHE_ENABLED and roles:
        role_data = [
            {
                "id": str(role.id),
                "name": role.name,
                "description": role.description,
                "domain": role.domain,
                "is_system_role": role.is_system_role,
            }
            for role in roles
        ]
        await set_cached_roles(user_id_str, role_data)

    return roles


async def get_user_permissions(
    session: AsyncSession,
    user_id: UUID,
    team_id: Optional[UUID] = None,
    domain: Optional[str] = None,
) -> List[Permission]:
    """Get all permissions granted to a user through their roles."""
    # Check L1/L2 cache first
    if settings.USER_CACHE_ENABLED:
        cached = await user_auth_cache.get_permissions(str(user_id))
        if cached is not None:
            return [Permission(**p) for p in cached]

    # Get user's roles
    roles = await get_user_roles(session, user_id, team_id=team_id, domain=domain)
    if not roles:
        return []

    role_ids = [role.id for role in roles]

    # Get permissions for these roles
    query = (
        select(Permission)
        .join(RolePermission)
        .where(cast(Any, RolePermission.role_id).in_(role_ids))
    )

    result = await session.execute(query)
    permissions = list(result.scalars().unique().all())

    # Store in cache
    if settings.USER_CACHE_ENABLED and permissions:
        perm_data = [
            {
                "id": str(permission.id),
                "name": permission.name,
                "description": permission.description,
                "resource_type": permission.resource_type,
                "action": permission.action,
            }
            for permission in permissions
        ]
        await user_auth_cache.set_permissions(str(user_id), perm_data)

    return permissions


async def has_permission(
    session: AsyncSession,
    user: User,
    permission_name: str,
    team_id: Optional[UUID] = None,
) -> bool:
    """Check if a user has a specific permission."""
    # Superusers have all permissions (for backward compatibility during migration)
    if user.is_superuser:
        return True

    permissions = await get_user_permissions(session, user.id, team_id=team_id)
    return permission_name in {permission.name for permission in permissions}


async def has_role(
    session: AsyncSession,
    user: User,
    role_name: str,
    team_id: Optional[UUID] = None,
    domain: Optional[str] = None,
) -> bool:
    """Check if a user has a specific role."""
    roles = await get_user_roles(session, user.id, team_id=team_id, domain=domain)
    return role_name in {role.name for role in roles}


async def check_team_permission(
    session: AsyncSession,
    user: User,
    team_id: UUID,
    permission_name: str,
) -> bool:
    """Check if a user has a permission within a specific team.

    This checks:
    1. If user is a member of the team
    2. If user's team role has the permission
    3. If user has global permission (fallback)
    """
    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Check if user is a team member
    query = select(TeamMember).where(
        TeamMember.team_id == team_id, TeamMember.user_id == user.id
    )
    result = await session.execute(query)
    team_member = result.scalar_one_or_none()

    if not team_member:
        return False

    # Check team-scoped permission
    if await has_permission(session, user, permission_name, team_id=team_id):
        return True

    # Fallback: check global permission
    return await has_permission(session, user, permission_name, team_id=None)
