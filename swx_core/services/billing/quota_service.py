"""
Quota Service
------------
Service for quota enforcement and feature entitlements.
"""

from uuid import UUID
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.billing.entitlement_resolver import EntitlementResolver
from swx_core.models.billing import BillingAccountType, UsageRecord, Feature


class QuotaExceededError(Exception):
    def __init__(self, feature: str, limit: int, current: int):
        self.feature = feature
        self.limit = limit
        self.current = current
        super().__init__(
            f"Quota exceeded for '{feature}': used {current} of {limit}"
        )


class EntitlementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.resolver = EntitlementResolver(session)
    
    async def require_quota(
        self,
        owner_id: UUID,
        account_type: BillingAccountType,
        feature_key: str,
        quantity: int = 1,
    ) -> int:
        remaining = await self.resolver.get_remaining_quota(
            owner_id, account_type, feature_key
        )
        
        if remaining < quantity:
            limit = await self._get_limit(owner_id, account_type, feature_key)
            used = limit - remaining if limit != -1 else remaining
            raise QuotaExceededError(feature_key, limit, used)
        
        return remaining - quantity
    
    async def require_feature(
        self,
        owner_id: UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> bool:
        has = await self.resolver.has(owner_id, account_type, feature_key)
        
        if not has:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature_key}' not available on your current plan",
            )
        
        return True
    
    async def check_feature(
        self,
        owner_id: UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> bool:
        return await self.resolver.has(owner_id, account_type, feature_key)
    
    async def get_remaining_quota(
        self,
        owner_id: UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> int:
        return await self.resolver.get_remaining_quota(
            owner_id, account_type, feature_key
        )
    
    async def _get_limit(
        self,
        owner_id: UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> int:
        limit_str = await self.resolver.get_entitlement(
            owner_id, account_type, feature_key
        )
        
        if not limit_str:
            return 0
        
        try:
            return int(limit_str)
        except ValueError:
            return 0


def require_quota_dependency(
    feature_key: str,
    quantity: int = 1,
):
    from swx_core.database.db import SessionDep
    from swx_core.auth.user.dependencies import UserDep
    from swx_core.core.tenant import get_current_team_id
    
    async def dependency(
        session: SessionDep,
        current_user: UserDep,
    ):
        service = EntitlementService(session)
        
        team_id = get_current_team_id()
        
        if team_id:
            owner_id = team_id
            account_type = BillingAccountType.TEAM
        else:
            owner_id = current_user.id
            account_type = BillingAccountType.USER
        
        remaining = await service.require_quota(
            owner_id, account_type, feature_key, quantity
        )
        
        return remaining
    
    return dependency


def require_feature_dependency(feature_key: str):
    from swx_core.database.db import SessionDep
    from swx_core.auth.user.dependencies import UserDep
    from swx_core.core.tenant import get_current_team_id
    
    async def dependency(
        session: SessionDep,
        current_user: UserDep,
    ):
        service = EntitlementService(session)
        
        team_id = get_current_team_id()
        
        if team_id:
            owner_id = team_id
            account_type = BillingAccountType.TEAM
        else:
            owner_id = current_user.id
            account_type = BillingAccountType.USER
        
        await service.require_feature(owner_id, account_type, feature_key)
        
        return True
    
    return dependency