"""
Billing Logic Integration
-------------------------
Helper functions to integrate billing checks into the system.
"""

from fastapi import HTTPException, status, Request
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
from swx_core.services.billing.entitlement_resolver import EntitlementResolver
from swx_core.models.billing import BillingAccountType

async def enforce_entitlement(
    request: Request,
    feature_key: str,
    session: SessionDep,
    current_user: UserDep,
    team_id: str = None
):
    """
    FastAPI dependency-like function to enforce an entitlement.
    """
    resolver = EntitlementResolver(session)
    
    # 1. Determine scope (Team or Individual)
    if team_id:
        owner_id = team_id
        account_type = BillingAccountType.TEAM
    else:
        owner_id = current_user.id
        account_type = BillingAccountType.USER
        
    # 2. Check entitlement
    has_access = await resolver.has(owner_id, account_type, feature_key)
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires the '{feature_key}' feature, which is not available on your current plan."
        )
    
    return True
