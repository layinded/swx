"""
SwX Core - Tenant Context
-------------------------
Multi-tenant support with context variables.
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

__all__ = [
    "set_current_tenant",
    "get_current_tenant_id",
    "clear_current_tenant",
    "tenant_context",
    "get_current_team_id",
    "set_current_team",
    "TenantContext",
]