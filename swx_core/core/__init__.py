"""
SwX Core - Tenant Context & Hooks
----------------------------------
Multi-tenant support with context variables and registration hooks.
"""

from swx_core.core.tenant import (
    set_current_tenant,
    get_current_tenant_id,
    clear_current_tenant,
    tenant_context,
    get_current_team_id,
    set_current_team,
    TenantContext,
)
from swx_core.core.hooks import registration_hooks, RegistrationHookRegistry

__all__ = [
    "set_current_tenant",
    "get_current_tenant_id",
    "clear_current_tenant",
    "tenant_context",
    "get_current_team_id",
    "set_current_team",
    "TenantContext",
    "registration_hooks",
    "RegistrationHookRegistry",
]