# swx_core/cli/commands/resource_templates.py

"""
Resource generation templates for SwX CLI.

This module provides two sets of templates:
1. Legacy templates - Static function-based patterns
2. Base class templates - Using BaseController/BaseService/BaseRepository (recommended)

Use --base flag with swx make:resource to use base class templates.
"""

# -------------------- Method Snippets for Extra Actions --------------------
METHOD_TEMPLATE = """
    @staticmethod
    def {method_name}(db: SessionDep, id: uuid.UUID, data: {schema_name}):
        \"\"\"Service layer: {method_name} for {name_lower} resource.\"\"\"
        return {repo_class}.{method_name}(db, id, data)
"""

CONTROLLER_METHOD_TEMPLATE = """
    @staticmethod
    def {method_name}(request: Request, id: uuid.UUID, data: {schema_name}, db: SessionDep):
        \"\"\"Controller: {method_name} for {name_lower} resource.\"\"\"
        return {service_class}.{method_name}(db, id, data)
"""

REPOSITORY_METHOD_TEMPLATE = """
    @staticmethod
    def {method_name}(db: SessionDep, id: uuid.UUID, data: {schema_name}):
        \"\"\"Repository method: {method_name} for {name_lower} resource.\"\"\"
        obj = db.get({model_class}, id)
        if not obj:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj
"""

ROUTE_METHOD_TEMPLATE = """
@router.put("/{{id}}/{method_name}", response_model={model_class}Public,
            summary="{method_name} for {name_lower}",
            description="{method_doc}")
def {method_name}(request: Request, id: uuid.UUID, data: {schema_name}, db: SessionDep):
    return {controller_class}.{method_name}(request, id, data, db)
"""

# ===================== Legacy Templates (Static Functions) =====================

LEGACY_TEMPLATES = {
    "controller": """{columns_comment}

from swx_core.database.db import SessionDep
from {module_path}.services.{service_file} import {service_class}
from {module_path}.models.{model_file} import {model_class}Create, {model_class}Update, {model_class}Public
from fastapi import HTTPException, Request
from swx_core.middleware.logging_middleware import logger
from swx_core.utils.language_helper import translate
import uuid

class {controller_class}:
    @staticmethod
    def retrieve_all_{name_lower}_resources(request: Request, db: SessionDep, skip: int = 0, limit: int = 100):
        \"\"\"Retrieve all {name_lower} resources with pagination.\"\"\"
        try:
            return {service_class}.retrieve_all_{name_lower}_resources(db, skip=skip, limit=limit)
        except Exception as e:
            logger.error("Error in retrieve_all_{name_lower}_resources: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    def retrieve_{name_lower}_by_id(request: Request, id: uuid.UUID, db: SessionDep):
        \"\"\"Retrieve a single {name_lower} resource by its ID.\"\"\" 
        item = {service_class}.retrieve_{name_lower}_by_id(db, id)
        if not item:
            raise HTTPException(status_code=404, detail=translate(request, f"{model_file}.not_found"))
        return item

    @staticmethod
    def create_new_{name_lower}(request: Request, data: {model_class}Create, db: SessionDep):
        \"\"\"Create a new {name_lower} resource.\"\"\" 
        try:
            return {service_class}.create_new_{name_lower}(db, data)
        except Exception as e:
            logger.error("Error in create_new_{name_lower}: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    def update_existing_{name_lower}(request: Request, id: uuid.UUID, data: {model_class}Update, db: SessionDep):
        \"\"\"Update an existing {name_lower} resource.\"\"\" 
        item = {service_class}.update_existing_{name_lower}(db, id, data)
        if not item:
            raise HTTPException(status_code=404, detail=translate(request, f"{model_file}.not_found"))
        return item

    @staticmethod
    def delete_existing_{name_lower}(request: Request, id: uuid.UUID, db: SessionDep):
        \"\"\"Delete an existing {name_lower} resource.\"\"\" 
        success = {service_class}.delete_existing_{name_lower}(db, id)
        if not success:
            raise HTTPException(status_code=404, detail=translate(request, f"{model_file}.not_found"))
        return None
{extra_controller_methods}
""",
    "route": """{columns_comment}
# SECURITY NOTE: Authentication is included by default but you should review and customize.
# Add RBAC permissions using: `from swx_core.rbac.dependencies import require_permission`
# Add policies using: `from swx_core.services.policy.dependencies import require_policy`

import uuid
from fastapi import APIRouter, Request, Depends, Query
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
# Optional: Add RBAC or policy dependencies
# from swx_core.rbac.dependencies import require_permission
# from swx_core.services.policy.dependencies import require_policy
from {module_path}.controllers.{controller_file} import {controller_class}
from {module_path}.models.{model_file} import {model_class}Create, {model_class}Update, {model_class}Public

router = APIRouter(prefix="/{model_file}")

# SECURITY: Routes are protected with UserDep authentication.
# Review and add RBAC permissions or policies as needed for your use case.

@router.get("/", response_model=list[{model_class}Public],
            summary="Get all {name_lower}",
            description="Retrieve all {name_lower} resources with optional pagination")
def get_all(request: Request, db: SessionDep, current_user: UserDep = Depends(),
            skip: int = Query(0, description="Number of items to skip"),
            limit: int = Query(100, description="Maximum number of items to return")):
    return {controller_class}.retrieve_all_{name_lower}_resources(request, db, skip=skip, limit=limit)

@router.get("/{{id}}", response_model={model_class}Public,
            summary="Get {name_lower} by ID",
            description="Retrieve a single {name_lower} resource by its unique identifier")
def get_by_id(request: Request, id: uuid.UUID, db: SessionDep, current_user: UserDep = Depends()):
    return {controller_class}.retrieve_{name_lower}_by_id(request, id, db)

@router.post("/", response_model={model_class}Public, status_code=201,
             summary="Create new {name_lower}",
             description="Create a new {name_lower} resource")
def create(request: Request, data: {model_class}Create, db: SessionDep, current_user: UserDep = Depends()):
    return {controller_class}.create_new_{name_lower}(request, data, db)

@router.put("/{{id}}", response_model={model_class}Public,
            summary="Update {name_lower}",
            description="Update an existing {name_lower} resource by ID")
def update(request: Request, id: uuid.UUID, data: {model_class}Update, db: SessionDep, current_user: UserDep = Depends()):
    return {controller_class}.update_existing_{name_lower}(request, id, data, db)

@router.delete("/{{id}}", status_code=204,
               summary="Delete {name_lower}",
               description="Delete an existing {name_lower} resource by ID")
def delete(request: Request, id: uuid.UUID, db: SessionDep, current_user: UserDep = Depends()):
    return {controller_class}.delete_existing_{name_lower}(request, id, db)
{extra_route_endpoints}
""",
    "repository": """{columns_comment}

import uuid
from sqlmodel import select
from swx_core.database.db import SessionDep
from {module_path}.models.{model_file} import {model_class}, {model_class}Create, {model_class}Update

class {repo_class}:
    @staticmethod
    def retrieve_all_{name_lower}_resources(db: SessionDep, skip: int = 0, limit: int = 100):
        \"\"\"Retrieve all {name_lower} resources with pagination.\"\"\" 
        query = select({model_class}).offset(skip).limit(limit)
        return db.exec(query).all()

    @staticmethod
    def retrieve_{name_lower}_by_id(db: SessionDep, id: uuid.UUID):
        \"\"\"Retrieve a single {name_lower} resource by ID.\"\"\" 
        return db.get({model_class}, id)

    @staticmethod
    def create_new_{name_lower}(db: SessionDep, data: {model_class}Create):
        \"\"\"Create a new {name_lower} resource in the database.\"\"\" 
        obj = {model_class}(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def update_existing_{name_lower}(db: SessionDep, id: uuid.UUID, data: {model_class}Update):
        \"\"\"Update an existing {name_lower} resource.\"\"\" 
        obj = db.get({model_class}, id)
        if not obj:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def delete_existing_{name_lower}(db: SessionDep, id: uuid.UUID):
        \"\"\"Delete an existing {name_lower} resource.\"\"\" 
        obj = db.get({model_class}, id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True
{extra_repo_methods}
""",
    "service": """{columns_comment}

import uuid
from swx_core.database.db import SessionDep
from {module_path}.repositories.{repo_file} import {repo_class}
from {module_path}.models.{model_file} import {model_class}Create, {model_class}Update
{extra_imports}

class {service_class}:
    @staticmethod
    def retrieve_all_{name_lower}_resources(db: SessionDep, skip: int = 0, limit: int = 100):
        \"\"\"Service layer: retrieve all {name_lower} resources.\"\"\" 
        return {repo_class}.retrieve_all_{name_lower}_resources(db, skip=skip, limit=limit)

    @staticmethod
    def retrieve_{name_lower}_by_id(db: SessionDep, id: uuid.UUID):
        \"\"\"Service layer: retrieve a single {name_lower} resource by ID.\"\"\" 
        return {repo_class}.retrieve_{name_lower}_by_id(db, id)

    @staticmethod
    def create_new_{name_lower}(db: SessionDep, data: {model_class}Create):
        \"\"\"Service layer: create a new {name_lower} resource.\"\"\" 
        return {repo_class}.create_new_{name_lower}(db, data)

    @staticmethod
    def update_existing_{name_lower}(db: SessionDep, id: uuid.UUID, data: {model_class}Update):
        \"\"\"Service layer: update an existing {name_lower} resource.\"\"\" 
        return {repo_class}.update_existing_{name_lower}(db, id, data)

    @staticmethod
    def delete_existing_{name_lower}(db: SessionDep, id: uuid.UUID):
        \"\"\"Service layer: delete an existing {name_lower} resource.\"\"\" 
        return {repo_class}.delete_existing_{name_lower}(db, id)

{extra_methods}
""",
    "model": """\
# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class {class_name}Base(Base):
{columns_base_placeholder}

class {class_name}({class_name}Base, table=True):
    __tablename__ = "{table_name}"
    __table_args__ = {{"extend_existing": True}}

    id: Optional[int] = Field(default=None, primary_key=True)
{columns_placeholder}

class {class_name}Create(SQLModel):
{columns_create_placeholder}

class {class_name}Update(SQLModel):
{columns_update_placeholder}

class {class_name}Public({class_name}):
    pass
""",
}

# ===================== Base Class Templates (Recommended) =====================
# These templates use BaseController, BaseService, BaseRepository for rapid development

BASE_TEMPLATES = {
    "controller": """{columns_comment}
\"\"\"
{controller_class} - Controller for {name_lower} resources.

Uses BaseController for automatic CRUD operations with pagination, search,
and soft delete support. Override methods as needed for custom behavior.
\"\"\"
from fastapi import APIRouter, Depends, Query, Request
from uuid import UUID

from swx_core.controllers.base import BaseController
from swx_core.database.db import SessionDep
from swx_core.auth.user.dependencies import UserDep
from {module_path}.models.{model_file} import {model_class}, {model_class}Create, {model_class}Update, {model_class}Public
from {module_path}.services.{service_file} import {service_class}
from {module_path}.repositories.{repo_file} import {repo_class}


class {controller_class}(BaseController[{model_class}, {model_class}Create, {model_class}Update, {model_class}Public]):
    \"\"\"
    Controller for {name_lower} resources with automatic CRUD endpoints.
    
    Inherits from BaseController which provides:
    - list(): Get all with pagination
    - get(): Get by ID
    - create(): Create new resource
    - update(): Update existing resource
    - delete(): Delete resource
    - search(): Full-text search
    - bulk_create(): Create multiple
    - bulk_update(): Update multiple
    - bulk_delete(): Delete multiple
    \"\"\"
    
    def __init__(self):
        super().__init__(
            model={model_class},
            schema_public={model_class}Public,
            schema_create={model_class}Create,
            schema_update={model_class}Update,
            prefix="/{model_file}",
            tags=["{model_class}"],
            service={service_class}({repo_class}()),
            repository={repo_class}(),
        )
        self.register_routes()
    
    def register_routes(self):
        \"\"\"Register custom routes. Standard CRUD routes are handled by BaseController.\"\"\"
        # Standard CRUD routes are automatically registered
        # Override this method to add custom routes
        
        # Example custom route:
        # @self.router.get("/search")
        # async def search_products(q: str = Query(...), skip: int = 0, limit: int = 100):
        #     return await self.search(q, ["name", "description"], skip, limit)
        pass


# Create controller instance
controller = {controller_class}()

# Export router for dynamic loading
router = controller.router
{extra_controller_methods}
""",

    "repository": """{columns_comment}
\"\"\"
{repo_class} - Repository for {name_lower} data access.

Uses BaseRepository for automatic CRUD, pagination, search, and soft delete.
Add custom query methods as needed.
\"\"\"
from uuid import UUID
from typing import Optional, List

from swx_core.repositories.base import BaseRepository
from swx_core.database.db import SessionDep
from {module_path}.models.{model_file} import {model_class}, {model_class}Create, {model_class}Update


class {repo_class}(BaseRepository[{model_class}]):
    \"\"\"
    Repository for {model_class} with automatic CRUD operations.
    
    Inherits from BaseRepository which provides:
    - find_by_id(id): Get by ID
    - find_all(skip, limit): Get all with pagination
    - find_by(**filters): Filter by fields
    - search(query, fields): Full-text search
    - create(data): Create new record
    - update(id, data): Update record
    - delete(id): Hard delete
    - soft_delete(id): Soft delete (requires is_deleted field)
    - restore(id): Restore soft-deleted
    - count(**filters): Count records
    - exists(id): Check existence
    - paginate(page, per_page): Paginated results
    \"\"\"
    
    def __init__(self):
        super().__init__(model={model_class})
    
    # Add custom repository methods here
    # Example:
    # async def find_by_name(self, name: str) -> Optional[{model_class}]:
    #     return await self.find_one_by(name=name)
    #
    # async def search_by_name(self, query: str) -> List[{model_class}]:
    #     return await self.search(query, ["name", "description"])
{extra_repo_methods}
""",

    "service": """{columns_comment}
\"\"\"
{service_class} - Service for {name_lower} business logic.

Uses BaseService for automatic CRUD with event emission, validation,
and lifecycle hooks. Add custom business logic as needed.
\"\"\"
from uuid import UUID
from typing import Optional

from swx_core.services.base import BaseService
from swx_core.database.db import SessionDep
from {module_path}.repositories.{repo_file} import {repo_class}
from {module_path}.models.{model_file} import {model_class}, {model_class}Create, {model_class}Update
{extra_imports}


class {service_class}(BaseService[{model_class}, {repo_class}]):
    \"\"\"
    Service for {model_class} with automatic CRUD and event emission.
    
    Inherits from BaseService which provides:
    - get(id): Get by ID
    - get_or_fail(id): Get or raise error
    - list(skip, limit): Get all with pagination
    - find_by(**filters): Filter records
    - search(query, fields): Full-text search
    - create(data): Create with events
    - update(id, data): Update with events
    - delete(id): Delete with events
    - soft_delete(id): Soft delete
    - restore(id): Restore deleted
    
    Lifecycle hooks (override as needed):
    - validate_create(data): Validate before creation
    - validate_update(instance, data): Validate before update
    - before_create(data): Pre-creation hook
    - after_create(instance): Post-creation hook
    - before_update(instance, data): Pre-update hook
    - after_update(old, new): Post-update hook
    - before_delete(instance): Pre-deletion hook
    - after_deleted(instance): Post-deletion hook
    \"\"\"
    
    def __init__(self, repository: {repo_class} = None):
        super().__init__(repository=repository or {repo_class}())
    
    # Override validation hooks if needed
    # async def validate_create(self, data: dict) -> None:
    #     # Add validation logic
    #     if await self.repository.exists_by(name=data.get('name')):
    #         raise ValueError("Name already exists")
    #
    # async def validate_update(self, instance: {model_class}, data: dict) -> None:
    #     # Add update validation
    #     pass
    
    # Override lifecycle hooks if needed
    # async def after_create(self, instance: {model_class}) -> None:
    #     # Send notifications, update indexes, etc.
    #     await self.event_bus.emit("{name_lower}.created", {{"id": str(instance.id)}})
{extra_methods}
""",

    "route": """{columns_comment}
\"\"\"
{model_class} routes - Automatic CRUD endpoints.

Routes using BaseController which automatically registers:
- GET /{model_file} - List all with pagination
- GET /{model_file}/{{id}} - Get by ID  
- POST /{model_file} - Create new
- PUT /{model_file}/{{id}} - Update existing
- DELETE /{model_file}/{{id}} - Delete

The controller handles all CRUD operations. Add custom routes in the controller.
\"\"\"
# Routes are automatically registered by the controller.
# See {module_path}.controllers.{controller_file} for the controller implementation.
#
# The controller exports a 'router' attribute that is automatically
# picked up by the SwX route discovery system.
#
# To add custom routes, edit the controller's register_routes() method.
{extra_route_endpoints}
""",

    "model": """\
# This model was generated using swx CLI with base class support.
# Recommended: Use model mixins from swx_core.utils.mixins for common fields.

from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

# Option 1: Use FullModelMixin (recommended for production)
# Includes: id (UUID), created_at, updated_at, is_deleted
# from swx_core.utils.mixins import FullModelMixin
# class {class_name}(FullModelMixin, table=True):

# Option 2: Use individual mixins
# from swx_core.utils.mixins import TimestampMixin, SoftDeleteMixin, UUIDPrimaryKeyMixin
# class {class_name}(TimestampMixin, SoftDeleteMixin, UUIDPrimaryKeyMixin, table=True):

# Option 3: Custom fields (shown below)
class {class_name}Base(SQLModel):
    \"\"\"Base model with shared fields.\"\"\"
{columns_base_placeholder}

class {class_name}({class_name}Base, table=True):
    \"\"\"
    {class_name} model.
    
    Fields:
        id: UUID primary key
        created_at: Creation timestamp
        updated_at: Last update timestamp
        is_deleted: Soft delete flag
    \"\"\"
    __tablename__ = "{table_name}"
    __table_args__ = {{"extend_existing": True}}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False, index=True)
{columns_placeholder}

class {class_name}Create(SQLModel):
    \"\"\"Schema for creating a new {class_name}.\"\"\"
{columns_create_placeholder}

class {class_name}Update(SQLModel):
    \"\"\"Schema for updating an existing {class_name}.\"\"\"
{columns_update_placeholder}

class {class_name}Public({class_name}Base):
    \"\"\"Public schema for {class_name} responses.\"\"\"
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
""",
}

# Alias for backward compatibility
TEMPLATES = LEGACY_TEMPLATES