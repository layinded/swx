"""
Base Service
------------
Generic service providing common business logic operations.

Usage:
    class ProductService(BaseService[Product]):
        def __init__(self):
            super().__init__(repository=ProductRepository())
        
        async def get_by_sku(self, sku: str) -> Optional[Product]:
            return await self.repository.find_by_field("sku", sku)
"""

import uuid
from typing import TypeVar, Generic, Dict, Any, Optional, List

from swx_core.repositories.base import BaseRepository
from swx_core.events import EventBus, Event
from swx_core.models.base import Base


# Type variables
ModelType = TypeVar("ModelType", bound=Base)
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[ModelType, RepositoryType]):
    """
    Base service providing common business logic operations.
    
    This service follows the Service pattern and provides:
    - CRUD operations with event emission
    - Business logic hooks
    - Transaction management
    - Validation hooks
    
    Usage:
        class ProductService(BaseService[Product, ProductRepository]):
            def __init__(self):
                super().__init__(repository=ProductRepository())
            
            async def create(self, data: Dict[str, Any], emit_event: bool = True) -> Product:
                # Custom validation
                if await self.repository.exists_by(sku=data.get('sku')):
                    raise ValueError("Product with this SKU already exists")
                
                # Call parent create
                product = await super().create(data, emit_event)
                
                # Additional business logic
                await self.event_bus.emit(Event(
                    name="product.inventory.created",
                    payload={"product_id": str(product.id), "initial_stock": data.get('quantity', 0)}
                ))
                
                return product
    """
    
    def __init__(self, repository: RepositoryType):
        """
        Initialize the service with a repository.
        
        Args:
            repository: The repository instance for data access
        """
        self.repository = repository
        self.event_bus = EventBus()
    
    # =========================================================================
    # Read Operations
    # =========================================================================
    
    async def get(self, id: uuid.UUID) -> Optional[ModelType]:
        """
        Get a record by ID.
        
        Args:
            id: The record ID
            
        Returns:
            The model instance or None
        """
        return await self.repository.find_by_id(id)
    
    async def get_or_fail(self, id: uuid.UUID) -> ModelType:
        """
        Get a record by ID or raise an exception.
        
        Args:
            id: The record ID
            
        Returns:
            The model instance
            
        Raises:
            ValueError: If record not found
        """
        return await self.repository.find_by_id_or_fail(id)
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> List[ModelType]:
        """
        List all records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by
            descending: Sort descending if True
            
        Returns:
            List of model instances
        """
        return await self.repository.find_all(
            skip=skip,
            limit=limit,
            order_by=order_by,
            descending=descending,
        )
    
    async def find_by(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Dict[str, Any],
    ) -> List[ModelType]:
        """
        Find records by filters.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Field-value pairs to filter by
            
        Returns:
            List of model instances
        """
        return await self.repository.find_by(skip=skip, limit=limit, **filters)
    
    async def find_one_by(self, **filters: Dict[str, Any]) -> Optional[ModelType]:
        """
        Find a single record by filters.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            Model instance or None
        """
        return await self.repository.find_one_by(**filters)
    
    async def search(
        self,
        query: str,
        fields: List[str],
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        """
        Search records by text query across specified fields.
        
        Args:
            query: Search query string
            fields: List of field names to search in
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of matching model instances
        """
        return await self.repository.search(query, fields, skip, limit)
    
    # =========================================================================
    # Write Operations
    # =========================================================================
    
    async def create(
        self,
        data: Dict[str, Any],
        emit_event: bool = True,
        validate: bool = True,
    ) -> ModelType:
        """
        Create a new record.
        
        Args:
            data: Dictionary of field values
            emit_event: Whether to emit a creation event
            validate: Whether to run validation hooks
            
        Returns:
            The created model instance
        """
        # Pre-create hook
        data = await self.before_create(data)
        
        # Validation
        if validate:
            await self.validate_create(data)
        
        # Create record
        instance = await self.repository.create(data)
        
        # Post-create hook
        await self.after_create(instance)
        
        # Emit event
        if emit_event:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.created",
                payload={"id": str(instance.id), "data": data},
            ))
        
        return instance
    
    async def update(
        self,
        id: uuid.UUID,
        data: Dict[str, Any],
        emit_event: bool = True,
        validate: bool = True,
    ) -> Optional[ModelType]:
        """
        Update a record.
        
        Args:
            id: The record ID
            data: Dictionary of fields to update
            emit_event: Whether to emit an update event
            validate: Whether to run validation hooks
            
        Returns:
            The updated model instance or None
        """
        # Get existing record
        instance = await self.repository.find_by_id(id)
        if not instance:
            return None
        
        # Pre-update hook
        data = await self.before_update(instance, data)
        
        # Validation
        if validate:
            await self.validate_update(instance, data)
        
        # Store old values for event
        old_values = {field: getattr(instance, field) for field in data.keys() if hasattr(instance, field)}
        
        # Update record
        updated = await self.repository.update(id, data)
        
        # Post-update hook
        if updated:
            await self.after_update(instance, updated)
        
        # Emit event
        if emit_event and updated:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.updated",
                payload={
                    "id": str(id),
                    "old_values": old_values,
                    "new_values": data,
                },
            ))
        
        return updated
    
    async def delete(
        self,
        id: uuid.UUID,
        emit_event: bool = True,
    ) -> bool:
        """
        Delete a record (hard delete).
        
        Args:
            id: The record ID
            emit_event: Whether to emit a deletion event
            
        Returns:
            True if deleted, False if not found
        """
        # Get existing record for event
        instance = await self.repository.find_by_id(id)
        if not instance:
            return False
        
        # Pre-delete hook
        await self.before_delete(instance)
        
        # Delete record
        success = await self.repository.delete(id)
        
        # Post-delete hook
        if success:
            await self.after_deleted(instance)
        
        # Emit event
        if emit_event and success:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.deleted",
                payload={"id": str(id)},
            ))
        
        return success
    
    async def soft_delete(
        self,
        id: uuid.UUID,
        emit_event: bool = True,
    ) -> Optional[ModelType]:
        """
        Soft delete a record.
        
        Requires model to have 'is_deleted' field.
        
        Args:
            id: The record ID
            emit_event: Whether to emit a deletion event
            
        Returns:
            The soft-deleted model instance or None
        """
        instance = await self.repository.find_by_id(id)
        if not instance:
            return None
        
        # Pre-delete hook
        await self.before_soft_delete(instance)
        
        # Soft delete
        updated = await self.repository.soft_delete(id)
        
        # Post-delete hook
        if updated:
            await self.after_soft_deleted(updated)
        
        # Emit event
        if emit_event and updated:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.soft_deleted",
                payload={"id": str(id)},
            ))
        
        return updated
    
    async def restore(
        self,
        id: uuid.UUID,
        emit_event: bool = True,
    ) -> Optional[ModelType]:
        """
        Restore a soft-deleted record.
        
        Args:
            id: The record ID
            emit_event: Whether to emit a restoration event
            
        Returns:
            The restored model instance or None
        """
        # Restore
        restored = await self.repository.restore(id)
        
        # Post-restore hook
        if restored:
            await self.after_restored(restored)
        
        # Emit event
        if emit_event and restored:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.restored",
                payload={"id": str(id)},
            ))
        
        return restored
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    async def bulk_create(
        self,
        data_list: List[Dict[str, Any]],
        emit_event: bool = True,
    ) -> List[ModelType]:
        """
        Create multiple records at once.
        
        Args:
            data_list: List of dictionaries with field values
            emit_event: Whether to emit events
            
        Returns:
            List of created model instances
        """
        # Pre-create hooks
        processed_data = []
        for data in data_list:
            processed_data.append(await self.before_create(data))
        
        # Create records
        instances = await self.repository.create_many(processed_data)
        
        # Post-create hooks
        for instance in instances:
            await self.after_create(instance)
        
        # Emit event
        if emit_event:
            model_name = self.repository.model.__name__.lower()
            await self.event_bus.emit(Event(
                name=f"{model_name}.bulk_created",
                payload={"count": len(instances)},
            ))
        
        return instances
    
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
        return await self.repository.count(**filters)
    
    async def exists(self, id: uuid.UUID) -> bool:
        """
        Check if a record exists.
        
        Args:
            id: The record ID
            
        Returns:
            True if exists, False otherwise
        """
        return await self.repository.exists(id)
    
    async def exists_by(self, **filters: Dict[str, Any]) -> bool:
        """
        Check if records matching filters exist.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            True if exists, False otherwise
        """
        return await self.repository.exists_by(**filters)
    
    # =========================================================================
    # Pagination
    # =========================================================================
    
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
        return await self.repository.paginate(
            page=page,
            per_page=per_page,
            order_by=order_by,
            descending=descending,
            **filters,
        )
    
    # =========================================================================
    # Validation Hooks (Override in subclasses)
    # =========================================================================
    
    async def validate_create(self, data: Dict[str, Any]) -> None:
        """
        Validate data before creation. Override in subclasses.
        
        Args:
            data: Dictionary of field values
            
        Raises:
            ValueError: If validation fails
        """
        pass
    
    async def validate_update(self, instance: ModelType, data: Dict[str, Any]) -> None:
        """
        Validate data before update. Override in subclasses.
        
        Args:
            instance: Current model instance
            data: Dictionary of fields to update
            
        Raises:
            ValueError: If validation fails
        """
        pass
    
    # =========================================================================
    # Lifecycle Hooks (Override in subclasses)
    # =========================================================================
    
    async def before_create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook called before creation. Override in subclasses.
        
        Args:
            data: Dictionary of field values
            
        Returns:
            Modified data dictionary
        """
        return data
    
    async def after_create(self, instance: ModelType) -> None:
        """
        Hook called after creation. Override in subclasses.
        
        Args:
            instance: The created model instance
        """
        pass
    
    async def before_update(self, instance: ModelType, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook called before update. Override in subclasses.
        
        Args:
            instance: Current model instance
            data: Dictionary of fields to update
            
        Returns:
            Modified data dictionary
        """
        return data
    
    async def after_update(self, old_instance: ModelType, new_instance: ModelType) -> None:
        """
        Hook called after update. Override in subclasses.
        
        Args:
            old_instance: The old model instance
            new_instance: The updated model instance
        """
        pass
    
    async def before_delete(self, instance: ModelType) -> None:
        """
        Hook called before hard delete. Override in subclasses.
        
        Args:
            instance: The model instance to be deleted
        """
        pass
    
    async def after_deleted(self, instance: ModelType) -> None:
        """
        Hook called after hard delete. Override in subclasses.
        
        Args:
            instance: The deleted model instance
        """
        pass
    
    async def before_soft_delete(self, instance: ModelType) -> None:
        """
        Hook called before soft delete. Override in subclasses.
        
        Args:
            instance: The model instance to be soft-deleted
        """
        pass
    
    async def after_soft_deleted(self, instance: ModelType) -> None:
        """
        Hook called after soft delete. Override in subclasses.
        
        Args:
            instance: The soft-deleted model instance
        """
        pass
    
    async def after_restored(self, instance: ModelType) -> None:
        """
        Hook called after restore. Override in subclasses.
        
        Args:
            instance: The restored model instance
        """
        pass