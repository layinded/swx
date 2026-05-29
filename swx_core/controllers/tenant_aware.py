"""
Tenant-Aware Controller
----------------------
Base controller with automatic tenant context injection.
"""

import uuid
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status

from swx_core.controllers.base import BaseController
from swx_core.repositories.tenant_aware import TenantAwareRepository
from swx_core.services.base import BaseService
from swx_core.core.tenant import get_current_tenant_id, get_current_team_id
from swx_core.database.db import get_session
from swx_core.utils.pagination import PaginatedResponse, PaginationParams


ModelType = TypeVar("ModelType")
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")
PublicSchema = TypeVar("PublicSchema")


class TenantAwareController(
    BaseController[ModelType, CreateSchema, UpdateSchema, PublicSchema]
):
    def __init__(
        self,
        model: Type[ModelType],
        schema_public: Type[PublicSchema],
        schema_create: Optional[Type[CreateSchema]] = None,
        schema_update: Optional[Type[UpdateSchema]] = None,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        tenant_field: str = "tenant_id",
        team_field: str = "team_id",
        service: Optional[BaseService] = None,
    ):
        super().__init__(
            model=model,
            schema_public=schema_public,
            schema_create=schema_create,
            schema_update=schema_update,
            prefix=prefix,
            tags=tags,
            service=service,
        )
        
        self.tenant_field = tenant_field
        self.team_field = team_field
        
        self.repository = TenantAwareRepository(
            model=model,
            tenant_field=tenant_field,
            team_field=team_field,
        )
        
        if service is None:
            self.service = BaseService(self.repository)
    
    def _inject_tenant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = data.copy()
        tenant_id = get_current_tenant_id()
        team_id = get_current_team_id()
        
        if tenant_id and hasattr(self.model, self.tenant_field):
            if self.tenant_field not in result:
                result[self.tenant_field] = tenant_id
        
        if team_id and hasattr(self.model, self.team_field):
            if self.team_field not in result:
                result[self.team_field] = team_id
        
        return result
    
    async def create(self, data: Dict[str, Any]) -> PublicSchema:
        injected_data = self._inject_tenant_data(data)
        instance = await self.repository.create(injected_data)
        return self.schema_public.model_validate(instance)
    
    async def update(
        self, id: uuid.UUID, data: Dict[str, Any]
    ) -> Optional[PublicSchema]:
        instance = await self.repository.update(id, data)
        if instance:
            return self.schema_public.model_validate(instance)
        return None
    
    async def delete(self, id: uuid.UUID) -> bool:
        return await self.repository.delete(id)
    
    async def get(self, id: uuid.UUID) -> Optional[PublicSchema]:
        instance = await self.repository.find_by_id(id)
        if instance:
            return self.schema_public.model_validate(instance)
        return None
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> PaginatedResponse[PublicSchema]:
        items = await self.repository.find_all(
            skip=skip,
            limit=limit,
            order_by=order_by,
            descending=descending,
        )
        
        items = [self.schema_public.model_validate(item) for item in items]
        
        return PaginatedResponse(
            items=items,
            total=len(items),
            page=(skip // limit) + 1 if limit > 0 else 1,
            per_page=limit,
        )