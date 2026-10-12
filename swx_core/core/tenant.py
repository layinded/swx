"""
Tenant Context Module
---------------------
Multi-tenant context management using Python contextvars.

This module provides request-scoped tenant context that propagates
through async/await boundaries safely.

Usage:
    from swx_core.core.tenant import (
        set_current_tenant,
        get_current_tenant_id,
        tenant_context,
    )

    # In middleware
    set_current_tenant(user.tenant_id)

    # In repository/service
    tenant_id = get_current_tenant_id()

    # Temporary context switch
    with tenant_context(new_tenant_id):
        # Queries run in different tenant context
        pass
"""

from contextvars import ContextVar, Token
from contextlib import contextmanager
from typing import Optional
from uuid import UUID
from dataclasses import dataclass


# Sentinel value to distinguish "unset" from "explicitly None"
_UNSET = object()


# =============================================================================
# Tenant Context Variables
# =============================================================================

# Primary tenant context
_current_tenant_id: ContextVar[UUID | object] = ContextVar(
    "current_tenant_id",
    default=_UNSET
)

# Team context (for team-scoped operations)
_current_team_id: ContextVar[UUID | object] = ContextVar(
    "current_team_id",
    default=_UNSET
)

# Super-admin bypass flag
_is_super_admin: ContextVar[bool] = ContextVar(
    "is_super_admin",
    default=False
)


# =============================================================================
# Tenant Context Info
# =============================================================================

@dataclass
class TenantContext:
    """
    Complete tenant context information.
    
    Attributes:
        tenant_id: Primary tenant/organization ID
        team_id: Optional team ID for team-scoped operations
        is_super_admin: Whether current user is super admin (bypasses tenant filter)
    """
    tenant_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    is_super_admin: bool = False


# =============================================================================
# Tenant Context Functions
# =============================================================================

def set_current_tenant(tenant_id: UUID | None) -> None:
    """
    Set the current tenant context.
    
    Args:
        tenant_id: The tenant/organization ID, or None to clear
    """
    _current_tenant_id.set(tenant_id if tenant_id is not None else _UNSET)


def get_current_tenant_id() -> UUID | None:
    """
    Get the current tenant ID from context.
    
    Returns:
        The tenant ID, or None if not set
    """
    val = _current_tenant_id.get()
    return None if val is _UNSET else val


def set_current_team(team_id: UUID | None) -> None:
    """
    Set the current team context.
    
    Args:
        team_id: The team ID, or None to clear
    """
    _current_team_id.set(team_id if team_id is not None else _UNSET)


def get_current_team_id() -> UUID | None:
    """
    Get the current team ID from context.
    
    Returns:
        The team ID, or None if not set
    """
    val = _current_team_id.get()
    return None if val is _UNSET else val


def set_super_admin(is_super_admin: bool = True) -> None:
    """
    Set super-admin flag (bypasses tenant filtering).
    
    Args:
        is_super_admin: Whether current user is super admin
    """
    _is_super_admin.set(is_super_admin)


def is_super_admin() -> bool:
    """
    Check if current context is super admin.
    
    Returns:
        True if super admin (bypasses tenant filter)
    """
    return _is_super_admin.get()


def clear_current_tenant() -> None:
    """
    Clear all tenant context variables.
    
    IMPORTANT: Must be called in finally block of middleware
    to prevent context leakage between requests.
    """
    _current_tenant_id.set(_UNSET)
    _current_team_id.set(_UNSET)
    _is_super_admin.set(False)


# =============================================================================
# Context Managers
# =============================================================================

@contextmanager
def tenant_context(tenant_id: UUID | None, team_id: UUID | None = None):
    """
    Context manager for temporarily switching tenant context.
    
    Usage:
        with tenant_context(new_tenant_id):
            # Queries run in different tenant context
            result = await repository.find_all()
    
    Args:
        tenant_id: The tenant ID to switch to
        team_id: Optional team ID for team-scoped operations
    """
    tenant_token = _current_tenant_id.set(
        tenant_id if tenant_id is not None else _UNSET
    )
    team_token = _current_team_id.set(
        team_id if team_id is not None else _UNSET
    )
    
    try:
        yield
    finally:
        _current_tenant_id.reset(tenant_token)
        _current_team_id.reset(team_token)


@contextmanager
def super_admin_context():
    """
    Context manager for temporarily enabling super-admin mode.
    
    Usage:
        with super_admin_context():
            # Bypass tenant filtering
            all_records = await repository.find_all()
    """
    token = _is_super_admin.set(True)
    try:
        yield
    finally:
        _is_super_admin.reset(token)


# =============================================================================
# Utility Functions
# =============================================================================

def get_tenant_context() -> TenantContext:
    """
    Get complete tenant context info.
    
    Returns:
        TenantContext with all current context values
    """
    return TenantContext(
        tenant_id=get_current_tenant_id(),
        team_id=get_current_team_id(),
        is_super_admin=is_super_admin(),
    )


def set_tenant_context(
    tenant_id: UUID | None = None,
    team_id: UUID | None = None,
    is_super_admin: bool = False
) -> None:
    """
    Set complete tenant context at once.
    
    Args:
        tenant_id: The tenant/organization ID
        team_id: Optional team ID for team-scoped operations
        is_super_admin: Whether to bypass tenant filtering
    """
    set_current_tenant(tenant_id)
    set_current_team(team_id)
    set_super_admin(is_super_admin)