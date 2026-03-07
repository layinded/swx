"""
Base Controller
---------------
Base controller providing standard CRUD operations for FastAPI applications.

Usage:
    class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
        def __init__(self):
            super().__init__(
                model=Product,
                schema_public=ProductPublic,
                schema_create=ProductCreate,
                schema_update=ProductUpdate,
                prefix="/products",
                tags=["Products"]
            )
            
            # Register custom routes after initialization
            self.register_routes()
        
        def register_routes(self):
            @self.router.get("/search")
            async def search_products(q: str):
                return await self.service.search(q)
"""

import uuid
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Callable
from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy import select, func

from swx_core.database.db import get_session
from swx_core.repositories.base import BaseRepository
from swx_core.services.base import BaseService
from swx_core.utils.pagination import PaginatedResponse, PaginationParams
from swx_core.utils.response import APIResponse


# Type variables for generic typing
ModelType = TypeVar("ModelType")
CreateSchema = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema = TypeVar("UpdateSchema", bound=BaseModel)
PublicSchema = TypeVar("PublicSchema", bound=BaseModel)


class BaseController(Generic[ModelType, CreateSchema, UpdateSchema, PublicSchema]):
    """
    Base controller providing standard CRUD operations with pagination support.
    
    This controller follows the Controller-Service-Repository pattern:
    - Controller handles HTTP request/response
    - Service handles business logic
    - Repository handles data access
    
    Features:
    - Automatic CRUD endpoints
    - Pagination support
    - Filtering support
    - Soft delete support (if model has is_deleted field)
    - Audit logging support
    - Permission checking hooks
    
    Usage:
        class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
            def __init__(self):
                super().__init__(
                    model=Product,
                    schema_public=ProductPublic,
                    schema_create=ProductCreate,
                    schema_update=ProductUpdate,
                    prefix="/products",
                    tags=["Products"]
                )
    """
    
    def __init__(
        self,
        model: Type[ModelType],
        schema_public: Type[PublicSchema],
        schema_create: Optional[Type[CreateSchema]] = None,
        schema_update: Optional[Type[UpdateSchema]] = None,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        service: Optional[BaseService] = None,
        repository: Optional[BaseRepository] = None,
    ):
        """
        Initialize the base controller.
        
        Args:
            model: The SQLAlchemy model class
            schema_public: Pydantic schema for public responses
            schema_create: Pydantic schema for creation (optional)
            schema_update: Pydantic schema for updates (optional)
            prefix: Router prefix
            tags: OpenAPI tags
            service: Service instance (optional, will create if not provided)
            repository: Repository instance (optional, will create if not provided)
        """
        self.model = model
        self.schema_public = schema_public
        self.schema_create = schema_create
        self.schema_update = schema_update
        self.prefix = prefix
        self.tags = tags or [model.__name__]
        
        # Create router
        self.router = APIRouter(prefix=prefix, tags=self.tags)
        
        # Initialize repository if not provided
        if repository is None:
            from swx_core.repositories.base import BaseRepository
            self.repository = BaseRepository(model)
        else:
            self.repository = repository
        
        # Initialize service if not provided
        if service is None:
            from swx_core.services.base import BaseService
            self.service = BaseService(self.repository)
        else:
            self.service = service
    
    # =========================================================================
    # Read Operations
    # =========================================================================
    
    async def list(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
        order_by: str = Query("created_at", description="Field to order by"),
        descending: bool = Query(True, description="Sort descending"),
    ) -> PaginatedResponse[PublicSchema]:
        """
        List all records with pagination.
        
        Override this method to customize listing behavior.
        """
        items = await self.repository.find_all(
            skip=skip,
            limit=limit,
            order_by=order_by,
            descending=descending,
        )
        total = await self.repository.count()
        
        return PaginatedResponse.create(
            data=[self.schema_public.model_validate(item) for item in items],
            total=total,
            page=(skip // limit) + 1,
            per_page=limit,
        )
    
    async def get(
        self,
        id: uuid.UUID,
    ) -> PublicSchema:
        """
        Get a single record by ID.
        
        Override this method to customize retrieval behavior.
        """
        item = await self.repository.find_by_id(id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        return self.schema_public.model_validate(item)
    
    async def get_by(
        self,
        field: str,
        value: Any,
    ) -> PublicSchema:
        """
        Get a single record by a specific field.
        
        Override this method to customize retrieval behavior.
        """
        items = await self.repository.find_by(**{field: value}, limit=1)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        return self.schema_public.model_validate(items[0])
    
    # =========================================================================
    # Write Operations
    # =========================================================================
    
    async def create(
        self,
        data: CreateSchema,
        created_by_id: Optional[uuid.UUID] = None,
        emit_event: bool = True,
    ) -> PublicSchema:
        """
        Create a new record.
        
        Override this method to customize creation behavior.
        
        Args:
            data: Creation schema
            created_by_id: ID of the user creating the record
            emit_event: Whether to emit an event
        """
        # Convert schema to dict
        create_data = data.model_dump()
        
        # Add created_by if provided
        if created_by_id and hasattr(self.model, 'created_by_id'):
            create_data['created_by_id'] = created_by_id
        
        # Create through service
        item = await self.service.create(create_data, emit_event=emit_event)
        
        return self.schema_public.model_validate(item)
    
    async def update(
        self,
        id: uuid.UUID,
        data: UpdateSchema,
        emit_event: bool = True,
    ) -> PublicSchema:
        """
        Update a record.
        
        Override this method to customize update behavior.
        """
        # Convert schema to dict, excluding unset values
        update_data = data.model_dump(exclude_unset=True)
        
        # Update through service
        item = await self.service.update(id, update_data, emit_event=emit_event)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        
        return self.schema_public.model_validate(item)
    
    async def delete(
        self,
        id: uuid.UUID,
        soft_delete: bool = True,
        emit_event: bool = True,
    ) -> None:
        """
        Delete a record.
        
        Args:
            id: Record ID
            soft_delete: If True and model supports it, soft delete instead of hard delete
            emit_event: Whether to emit an event
        
        Override this method to customize deletion behavior.
        """
        # Check if record exists
        if not await self.repository.exists(id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        
        # Soft delete if supported and requested
        if soft_delete and hasattr(self.model, 'is_deleted'):
            await self.service.update(id, {'is_deleted': True}, emit_event=emit_event)
        else:
            await self.service.delete(id, emit_event=emit_event)
    
    async def restore(
        self,
        id: uuid.UUID,
        emit_event: bool = True,
    ) -> PublicSchema:
        """
        Restore a soft-deleted record.
        
        Only works if model has 'is_deleted' field.
        """
        if not hasattr(self.model, 'is_deleted'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This model does not support soft delete"
            )
        
        item = await self.service.update(id, {'is_deleted': False}, emit_event=emit_event)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        
        return self.schema_public.model_validate(item)
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    async def search(
        self,
        query: str,
        fields: List[str],
        skip: int = 0,
        limit: int = 100,
    ) -> PaginatedResponse[PublicSchema]:
        """
        Search records by text query across specified fields.
        """
        items = await self.repository.search(query, fields, skip, limit)
        total = await self.repository.count_search(query, fields)
        
        return PaginatedResponse.create(
            data=[self.schema_public.model_validate(item) for item in items],
            total=total,
            page=(skip // limit) + 1,
            per_page=limit,
        )
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    async def bulk_create(
        self,
        data_list: List[CreateSchema],
        created_by_id: Optional[uuid.UUID] = None,
    ) -> List[PublicSchema]:
        """
        Create multiple records at once.
        """
        items = []
        for data in data_list:
            create_data = data.model_dump()
            if created_by_id and hasattr(self.model, 'created_by_id'):
                create_data['created_by_id'] = created_by_id
            item = await self.service.create(create_data, emit_event=False)
            items.append(self.schema_public.model_validate(item))
        
        # Emit bulk event
        await self.service.event_bus.emit(
            f"{self.model.__name__.lower()}.bulk_created",
            {"count": len(items)}
        )
        
        return items
    
    async def bulk_update(
        self,
        ids: List[uuid.UUID],
        data: UpdateSchema,
    ) -> List[PublicSchema]:
        """
        Update multiple records at once.
        """
        update_data = data.model_dump(exclude_unset=True)
        items = []
        
        for id in ids:
            item = await self.service.update(id, update_data, emit_event=False)
            if item:
                items.append(self.schema_public.model_validate(item))
        
        await self.service.event_bus.emit(
            f"{self.model.__name__.lower()}.bulk_updated",
            {"count": len(items)}
        )
        
        return items
    
    async def bulk_delete(
        self,
        ids: List[uuid.UUID],
        soft_delete: bool = True,
    ) -> int:
        """
        Delete multiple records at once.
        """
        count = 0
        for id in ids:
            if soft_delete and hasattr(self.model, 'is_deleted'):
                await self.service.update(id, {'is_deleted': True}, emit_event=False)
            else:
                await self.service.delete(id, emit_event=False)
            count += 1
        
        await self.service.event_bus.emit(
            f"{self.model.__name__.lower()}.bulk_deleted",
            {"count": count}
        )
        
        return count
    
    # =========================================================================
    # Count Operations
    # =========================================================================
    
    async def count(
        self,
        **filters: Dict[str, Any],
    ) -> int:
        """
        Count records matching filters.
        """
        return await self.repository.count(**filters)
    
    async def exists(
        self,
        id: uuid.UUID,
    ) -> bool:
        """
        Check if a record exists.
        """
        return await self.repository.exists(id)
    
    # =========================================================================
    # Permission Helpers
    # =========================================================================
    
    def check_permission(
        self,
        user: Any,
        permission: str,
    ) -> bool:
        """
        Check if user has a specific permission.
        
        Override this method to implement custom permission logic.
        """
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        
        if hasattr(user, 'permissions'):
            return permission in user.permissions
        
        return False
    
    def require_permission(
        self,
        user: Any,
        permission: str,
    ) -> None:
        """
        Require a specific permission or raise 403.
        """
        if not self.check_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
    
    def check_ownership(
        self,
        user: Any,
        item: Any,
    ) -> bool:
        """
        Check if user owns an item.
        
        Override this method to implement custom ownership logic.
        """
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        
        if hasattr(item, 'user_id') and hasattr(user, 'id'):
            return str(item.user_id) == str(user.id)
        
        return False
    
    # =========================================================================
    # Route Registration
    # =========================================================================
    
    def register_routes(self) -> None:
        """
        Override this method to register custom routes.
        
        Called automatically after controller initialization.
        
        Example:
            def register_routes(self):
                @self.router.get("/search")
                async def search_products(q: str):
                    return await self.search(q, ["name", "description"])
        """
        pass
    
    def register_crud_routes(
        self,
        include_list: bool = True,
        include_get: bool = True,
        include_create: bool = True,
        include_update: bool = True,
        include_delete: bool = True,
        include_search: bool = False,
    ) -> None:
        """
        Register standard CRUD routes.
        
        This is an alternative to manually defining routes when you want
        automatic CRUD endpoints with customization options.
        """
        singular_name = self.model.__name__.lower()
        plural_name = f"{singular_name}s"
        
        if include_list:
            @self.router.get("", response_model=PaginatedResponse[self.schema_public])
            async def list_items(
                skip: int = Query(0, ge=0),
                limit: int = Query(100, ge=1, le=1000),
            ):
                return await self.list(skip=skip, limit=limit)
        
        if include_get:
            @self.router.get("/{id}", response_model=self.schema_public)
            async def get_item(id: uuid.UUID):
                return await self.get(id)
        
        if include_create and self.schema_create:
            @self.router.post("", response_model=self.schema_public, status_code=status.HTTP_201_CREATED)
            async def create_item(data: self.schema_create):
                return await self.create(data)
        
        if include_update and self.schema_update:
            @self.router.put("/{id}", response_model=self.schema_public)
            async def update_item(id: uuid.UUID, data: self.schema_update):
                return await self.update(id, data)
        
        if include_delete:
            @self.router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
            async def delete_item(id: uuid.UUID):
                await self.delete(id)
            
            # Add restore endpoint for soft-deleteable models
            if hasattr(self.model, 'is_deleted'):
                @self.router.post("/{id}/restore", response_model=self.schema_public)
                async def restore_item(id: uuid.UUID):
                    return await self.restore(id)
        
        if include_search:
            @self.router.get("/search", response_model=PaginatedResponse[self.schema_public])
            async def search_items(
                q: str = Query(..., min_length=1),
                skip: int = Query(0, ge=0),
                limit: int = Query(100, ge=1, le=1000),
            ):
                # Default search fields - override in subclass
                fields = ["name", "title", "description"] if hasattr(self.model, 'name') else []
                return await self.search(q, fields, skip, limit)