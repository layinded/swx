"""
Base Repository
---------------
Generic repository providing common data access operations.

Usage:
    class ProductRepository(BaseRepository[Product]):
        def __init__(self):
            super().__init__(model=Product)
        
        async def find_by_sku(self, sku: str) -> Optional[Product]:
            async with get_session() as session:
                query = select(Product).where(Product.sku == sku)
                result = await session.execute(query)
                return result.scalar_one_or_none()
"""

import uuid
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import BinaryExpression

from swx_core.database.db_setup import get_session
from swx_core.models.base import Base


# Type variable for model
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common data access operations.
    
    This repository follows the Repository pattern and provides:
    - CRUD operations
    - Pagination
    - Filtering
    - Searching
    - Bulk operations
    - Soft delete support
    
    Usage:
        class ProductRepository(BaseRepository[Product]):
            def __init__(self):
                super().__init__(model=Product)
            
            async def find_by_sku(self, sku: str) -> Optional[Product]:
                return await self.find_by_field("sku", sku)
            
            async def search_by_name(self, query: str) -> List[Product]:
                return await self.search(query, ["name", "description"])
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize the repository with a model class.
        
        Args:
            model: The SQLAlchemy model class
        """
        self.model = model
    
    # =========================================================================
    # Core Read Operations
    # =========================================================================
    
    async def find_by_id(self, id: uuid.UUID) -> Optional[ModelType]:
        """
        Find a single record by ID.
        
        Args:
            id: The record ID
            
        Returns:
            The model instance or None
        """
        async with get_session() as session:
            query = select(self.model).where(self.model.id == id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def find_by_id_or_fail(self, id: uuid.UUID) -> ModelType:
        """
        Find a single record by ID or raise an exception.
        
        Args:
            id: The record ID
            
        Returns:
            The model instance
            
        Raises:
            ValueError: If record not found
        """
        result = await self.find_by_id(id)
        if not result:
            raise ValueError(f"{self.model.__name__} with id {id} not found")
        return result
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> List[ModelType]:
        """
        Find all records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by
            descending: Sort descending if True
            
        Returns:
            List of model instances
        """
        async with get_session() as session:
            # Get order column
            order_column = getattr(self.model, order_by, None)
            if order_column is None:
                order_column = self.model.created_at if hasattr(self.model, 'created_at') else self.model.id
            
            # Build query
            query = select(self.model)
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                query = query.where(self.model.is_deleted == False)
            
            # Apply ordering
            if descending:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
            
            # Apply pagination
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
        """
        Find records by filters with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by
            descending: Sort descending if True
            **filters: Field-value pairs to filter by
            
        Returns:
            List of model instances
        """
        async with get_session() as session:
            query = select(self.model)
            
            # Apply filters
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                query = query.where(self.model.is_deleted == False)
            
            # Apply ordering
            order_column = getattr(self.model, order_by, self.model.created_at if hasattr(self.model, 'created_at') else self.model.id)
            if descending:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def find_one_by(**filters: Dict[str, Any]) -> Optional[ModelType]:
        """
        Find a single record by filters.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            Model instance or None
        """
        async with get_session() as session:
            query = select(self.model)
            
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            query = query.limit(1)
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    async def search(
        self,
        query: str,
        fields: List[str],
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        """
        Full-text search across specified fields.
        
        Args:
            query: Search query string
            fields: List of field names to search in
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of matching model instances
        """
        async with get_session() as session:
            # Build OR conditions for each field
            conditions = []
            for field in fields:
                if hasattr(self.model, field):
                    conditions.append(getattr(self.model, field).ilike(f"%{query}%"))
            
            if not conditions:
                return []
            
            # Build query
            stmt = select(self.model).where(or_(*conditions))
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                stmt = stmt.where(self.model.is_deleted == False)
            
            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)
            
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def count_search(
        self,
        query: str,
        fields: List[str],
    ) -> int:
        """
        Count records matching a search query.
        
        Args:
            query: Search query string
            fields: List of field names to search in
            
        Returns:
            Number of matching records
        """
        async with get_session() as session:
            # Build OR conditions for each field
            conditions = []
            for field in fields:
                if hasattr(self.model, field):
                    conditions.append(getattr(self.model, field).ilike(f"%{query}%"))
            
            if not conditions:
                return 0
            
            # Build count query
            stmt = select(func.count(self.model.id)).where(or_(*conditions))
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                stmt = stmt.where(self.model.is_deleted == False)
            
            result = await session.execute(stmt)
            return result.scalar() or 0
    
    # =========================================================================
    # Write Operations
    # =========================================================================
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Create a new record.
        
        Args:
            data: Dictionary of field values
            
        Returns:
            The created model instance
        """
        async with get_session() as session:
            # Set timestamps if model has them
            if hasattr(self.model, 'created_at') and 'created_at' not in data:
                data['created_at'] = datetime.utcnow()
            if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
                data['updated_at'] = datetime.utcnow()
            
            instance = self.model(**data)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
    
    async def create_many(self, data_list: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Create multiple records at once.
        
        Args:
            data_list: List of dictionaries with field values
            
        Returns:
            List of created model instances
        """
        async with get_session() as session:
            instances = []
            now = datetime.utcnow()
            
            for data in data_list:
                # Set timestamps if model has them
                if hasattr(self.model, 'created_at') and 'created_at' not in data:
                    data['created_at'] = now
                if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
                    data['updated_at'] = now
                
                instance = self.model(**data)
                session.add(instance)
                instances.append(instance)
            
            await session.commit()
            
            # Refresh all instances
            for instance in instances:
                await session.refresh(instance)
            
            return instances
    
    async def update(self, id: uuid.UUID, data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by ID.
        
        Args:
            id: The record ID
            data: Dictionary of fields to update
            
        Returns:
            The updated model instance or None
        """
        async with get_session() as session:
            query = select(self.model).where(self.model.id == id)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()
            
            if not instance:
                return None
            
            # Set updated_at timestamp
            if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
                data['updated_at'] = datetime.utcnow()
            
            # Update fields
            for field, value in data.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
    
    async def update_many(
        self,
        ids: List[uuid.UUID],
        data: Dict[str, Any],
    ) -> List[ModelType]:
        """
        Update multiple records by IDs.
        
        Args:
            ids: List of record IDs
            data: Dictionary of fields to update
            
        Returns:
            List of updated model instances
        """
        async with get_session() as session:
            query = select(self.model).where(self.model.id.in_(ids))
            result = await session.execute(query)
            instances = list(result.scalars().all())
            
            now = datetime.utcnow()
            if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
                data['updated_at'] = now
            
            for instance in instances:
                for field, value in data.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)
                session.add(instance)
            
            await session.commit()
            
            for instance in instances:
                await session.refresh(instance)
            
            return instances
    
    async def delete(self, id: uuid.UUID) -> bool:
        """
        Delete a record by ID (hard delete).
        
        Args:
            id: The record ID
            
        Returns:
            True if deleted, False if not found
        """
        async with get_session() as session:
            query = select(self.model).where(self.model.id == id)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()
            
            if not instance:
                return False
            
            await session.delete(instance)
            await session.commit()
            return True
    
    async def soft_delete(self, id: uuid.UUID) -> Optional[ModelType]:
        """
        Soft delete a record by ID.
        
        Requires model to have 'is_deleted' field.
        
        Args:
            id: The record ID
            
        Returns:
            The soft-deleted model instance or None
        """
        if not hasattr(self.model, 'is_deleted'):
            raise ValueError(f"{self.model.__name__} does not support soft delete")
        
        return await self.update(id, {'is_deleted': True})
    
    async def restore(self, id: uuid.UUID) -> Optional[ModelType]:
        """
        Restore a soft-deleted record.
        
        Requires model to have 'is_deleted' field.
        
        Args:
            id: The record ID
            
        Returns:
            The restored model instance or None
        """
        if not hasattr(self.model, 'is_deleted'):
            raise ValueError(f"{self.model.__name__} does not support soft delete")
        
        return await self.update(id, {'is_deleted': False})
    
    # =========================================================================
    # Count Operations
    # =========================================================================
    
    async def count(self, **filters: Dict[str, Any]) -> int:
        """
        Count records matching filters.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            Number of matching records
        """
        async with get_session() as session:
            query = select(func.count(self.model.id))
            
            # Apply filters
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                query = query.where(self.model.is_deleted == False)
            
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def exists(self, id: uuid.UUID) -> bool:
        """
        Check if a record exists.
        
        Args:
            id: The record ID
            
        Returns:
            True if exists, False otherwise
        """
        async with get_session() as session:
            query = select(func.count(self.model.id)).where(self.model.id == id)
            result = await session.execute(query)
            return (result.scalar() or 0) > 0
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    async def exists_by(**filters: Dict[str, Any]) -> bool:
        """
        Check if records matching filters exist.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            True if exists, False otherwise
        """
        async with get_session() as session:
            query = select(func.count(self.model.id))
            
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
            
            result = await session.execute(query)
            return (result.scalar() or 0) > 0
    
    async def get_field_values(
        self,
        field: str,
        distinct: bool = True,
    ) -> List[Any]:
        """
        Get all unique values for a specific field.
        
        Args:
            field: Field name
            distinct: Return distinct values only
            
        Returns:
            List of field values
        """
        async with get_session() as session:
            column = getattr(self.model, field)
            
            if distinct:
                query = select(column).distinct()
            else:
                query = select(column)
            
            # Filter soft-deleted records
            if hasattr(self.model, 'is_deleted'):
                query = query.where(self.model.is_deleted == False)
            
            result = await session.execute(query)
            return [row[0] for row in result.all()]
    
    async def bulk_update(
        self,
        filter_conditions: List[BinaryExpression],
        update_data: Dict[str, Any],
    ) -> int:
        """
        Bulk update records matching conditions.
        
        Args:
            filter_conditions: List of SQLAlchemy filter conditions
            update_data: Dictionary of fields to update
            
        Returns:
            Number of updated records
        """
        async with get_session() as session:
            from sqlalchemy import update as sql_update
            
            stmt = sql_update(self.model).where(and_(*filter_conditions)).values(**update_data)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
    
    async def bulk_delete(
        self,
        filter_conditions: List[BinaryExpression],
    ) -> int:
        """
        Bulk delete records matching conditions.
        
        Args:
            filter_conditions: List of SQLAlchemy filter conditions
            
        Returns:
            Number of deleted records
        """
        async with get_session() as session:
            from sqlalchemy import delete as sql_delete
            
            stmt = sql_delete(self.model).where(and_(*filter_conditions))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
    
    async def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
        order_by: str = "created_at",
        descending: bool = True,
        **filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get paginated results with metadata.
        
        Args:
            page: Page number (1-indexed)
            per_page: Records per page
            order_by: Field to order by
            descending: Sort descending if True
            **filters: Field-value pairs to filter by
            
        Returns:
            Dictionary with 'data', 'total', 'page', 'per_page', 'total_pages'
        """
        skip = (page - 1) * per_page
        
        # Get items
        items = await self.find_by(
            skip=skip,
            limit=per_page,
            order_by=order_by,
            descending=descending,
            **filters,
        )
        
        # Get total count
        total = await self.count(**filters)
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        return {
            'data': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        }