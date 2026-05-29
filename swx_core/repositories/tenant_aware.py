"""
Tenant-Aware Repository
----------------------
Repository with automatic tenant filtering via context variables.
"""

import uuid
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import BinaryExpression

from swx_core.repositories.base import BaseRepository
from swx_core.database.db import AsyncSessionLocal
from swx_core.models.base import Base
from swx_core.core.tenant import get_current_tenant_id, is_super_admin, get_current_team_id


ModelType = TypeVar("ModelType", bound=Base)


class TenantAwareRepository(BaseRepository[ModelType]):
    def __init__(
        self,
        model: Type[ModelType],
        tenant_field: str = "tenant_id",
        team_field: str = "team_id",
        session: Optional[AsyncSession] = None,
    ):
        super().__init__(model)
        self.tenant_field = tenant_field
        self.team_field = team_field
        self._external_session = session
    
    def _get_session(self):
        if self._external_session:
            return self._external_session
        return AsyncSessionLocal()
    
    def _apply_tenant_filter(self, query, use_team: bool = False):
        if is_super_admin():
            return query
        
        tenant_id = get_current_tenant_id()
        team_id = get_current_team_id()
        
        if use_team and team_id and hasattr(self.model, self.team_field):
            return query.where(getattr(self.model, self.team_field) == team_id)
        
        if tenant_id and hasattr(self.model, self.tenant_field):
            return query.where(getattr(self.model, self.tenant_field) == tenant_id)
        
        if team_id and hasattr(self.model, self.team_field):
            return query.where(getattr(self.model, self.team_field) == team_id)
        
        return query
    
    def _inject_tenant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        tenant_id = get_current_tenant_id()
        team_id = get_current_team_id()
        
        result = data.copy()
        
        if tenant_id and hasattr(self.model, self.tenant_field):
            if self.tenant_field not in result:
                result[self.tenant_field] = tenant_id
        
        if team_id and hasattr(self.model, self.team_field):
            if self.team_field not in result:
                result[self.team_field] = team_id
        
        return result
    
    async def find_by_id(self, id: uuid.UUID) -> Optional[ModelType]:
        async with self._get_session() as session:
            query = select(self.model).where(self.model.id == id)
            query = self._apply_tenant_filter(query)
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> List[ModelType]:
        async with self._get_session() as session:
            order_column = getattr(self.model, order_by, None)
            if order_column is None:
                order_column = (
                    self.model.created_at
                    if hasattr(self.model, "created_at")
                    else self.model.id
                )
            
            query = select(self.model)
            query = self._apply_tenant_filter(query)
            
            if hasattr(self.model, "is_deleted"):
                query = query.where(self.model.is_deleted == False)
            
            if descending:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
            
            query = query.offset(skip).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def find_by(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        descending: bool = True,
        **filters: Dict[str, Any],
    ) -> List[ModelType]:
        async with self._get_session() as session:
            query = select(self.model)
            query = self._apply_tenant_filter(query)
            
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            if hasattr(self.model, "is_deleted"):
                query = query.where(self.model.is_deleted == False)
            
            order_column = getattr(
                self.model,
                order_by,
                self.model.created_at if hasattr(self.model, "created_at") else self.model.id,
            )
            
            if descending:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
            
            query = query.offset(skip).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        data = self._inject_tenant_data(data)
        return await super().create(data)
    
    async def create_many(self, data_list: List[Dict[str, Any]]) -> List[ModelType]:
        injected_data = [self._inject_tenant_data(d) for d in data_list]
        return await super().create_many(injected_data)
    
    async def update(self, id: uuid.UUID, data: Dict[str, Any]) -> Optional[ModelType]:
        async with self._get_session() as session:
            query = select(self.model).where(self.model.id == id)
            query = self._apply_tenant_filter(query)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()
            
            if not instance:
                return None
            
            if hasattr(self.model, "updated_at") and "updated_at" not in data:
                data["updated_at"] = datetime.utcnow()
            
            for field, value in data.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
    
    async def delete(self, id: uuid.UUID) -> bool:
        async with self._get_session() as session:
            query = select(self.model).where(self.model.id == id)
            query = self._apply_tenant_filter(query)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()
            
            if not instance:
                return False
            
            await session.delete(instance)
            await session.commit()
            return True
    
    async def count(self, **filters: Dict[str, Any]) -> int:
        async with self._get_session() as session:
            query = select(func.count(self.model.id))
            query = self._apply_tenant_filter(query)
            
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            if hasattr(self.model, "is_deleted"):
                query = query.where(self.model.is_deleted == False)
            
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def exists(self, id: uuid.UUID) -> bool:
        async with self._get_session() as session:
            query = select(func.count(self.model.id)).where(self.model.id == id)
            query = self._apply_tenant_filter(query)
            result = await session.execute(query)
            return (result.scalar() or 0) > 0