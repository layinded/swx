# Base Classes (Controller-Service-Repository Pattern)

**Version:** 2.0.0  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [BaseRepository](#baserepository)
4. [BaseService](#baseservice)
5. [BaseController](#basecontroller)
6. [Quick Start](#quick-start)
7. [Complete Example](#complete-example)
8. [Best Practices](#best-practices)

---

## Overview

SwX provides base classes implementing the Controller-Service-Repository (CSR) pattern, offering:

- **BaseRepository** - Data access layer with CRUD operations
- **BaseService** - Business logic layer with event emission
- **BaseController** - HTTP layer with automatic endpoints

### Benefits

- **DRY** - Write CRUD operations once, reuse everywhere
- **Consistent** - Same patterns across all resources
- **Type-safe** - Generic typing for compile-time safety
- **Extensible** - Override methods for custom behavior
- **Event-driven** - Automatic event emission for auditing

---

## Architecture

```
┌─────────────────┐
│   Controller    │  ← HTTP request/response handling
└────────┬────────┘
         │
┌────────▼────────┐
│     Service     │  ← Business logic, validation, events
└────────┬────────┘
         │
┌────────▼────────┐
│   Repository    │  ← Database operations
└─────────────────┘
         │
┌────────▼────────┐
│      Model      │  ← Database table (SQLModel/SQLAlchemy)
└─────────────────┘
```

**Flow:**
1. Controller receives HTTP request
2. Controller calls Service methods
3. Service validates, executes business logic, emits events
4. Service calls Repository for data operations
5. Repository executes database queries
6. Response flows back up the chain

---

## BaseRepository

The `BaseRepository` provides common data access operations.

### Import

```python
from swx_core.repositories.base import BaseRepository
```

### Basic Usage

```python
from swx_core.repositories.base import BaseRepository
from swx_app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    """Repository for Product model."""
    
    def __init__(self):
        super().__init__(model=Product)
    
    async def find_by_sku(self, sku: str) -> Product | None:
        """Find product by SKU."""
        return await self.find_one_by(sku=sku)
    
    async def search_by_name(self, query: str) -> list[Product]:
        """Search products by name."""
        return await self.search(query, ["name", "description"])
```

### Available Methods

#### Read Operations

| Method | Description |
|--------|-------------|
| `find_by_id(id)` | Get single record by ID |
| `find_by_id_or_fail(id)` | Get record by ID or raise error |
| `find_all(skip, limit, order_by, descending)` | Get all records with pagination |
| `find_by(skip, limit, **filters)` | Get records by filters |
| `find_one_by(**filters)` | Get single record by filters |
| `search(query, fields, skip, limit)` | Full-text search |
| `count_search(query, fields)` | Count matching search results |

#### Write Operations

| Method | Description |
|--------|-------------|
| `create(data)` | Create new record |
| `create_many(data_list)` | Create multiple records |
| `update(id, data)` | Update record by ID |
| `update_many(ids, data)` | Update multiple records |
| `delete(id)` | Hard delete record |
| `soft_delete(id)` | Soft delete (requires `is_deleted` field) |
| `restore(id)` | Restore soft-deleted record |

#### Utility Operations

| Method | Description |
|--------|-------------|
| `count(**filters)` | Count records matching filters |
| `exists(id)` | Check if record exists |
| `exists_by(**filters)` | Check if matching records exist |
| `get_field_values(field, distinct)` | Get all values for a field |
| `paginate(page, per_page, **filters)` | Get paginated results with metadata |

### Example: Custom Repository

```python
from swx_core.repositories.base import BaseRepository
from swx_app.models.order import Order
from sqlalchemy import select

class OrderRepository(BaseRepository[Order]):
    """Repository for Order model with custom queries."""
    
    def __init__(self):
        super().__init__(model=Order)
    
    async def find_by_user(
        self, 
        user_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[Order]:
        """Find orders by user with optional status filter."""
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status
        
        return await self.find_by(skip=skip, limit=limit, **filters)
    
    async def count_pending(self) -> int:
        """Count pending orders."""
        return await self.count(status="pending")
    
    async def get_revenue_by_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate total revenue in a period."""
        # Custom query implementation
        async with get_session() as session:
            query = select(func.sum(Order.total)).where(
                Order.created_at >= start_date,
                Order.created_at <= end_date,
                Order.status == "completed"
            )
            result = await session.execute(query)
            return result.scalar() or 0.0
```

---

## BaseService

The `BaseService` provides business logic with event emission.

### Import

```python
from swx_core.services.base import BaseService
```

### Basic Usage

```python
from swx_core.services.base import BaseService
from swx_app.repositories.product_repository import ProductRepository

class ProductService(BaseService[Product, ProductRepository]):
    """Service for Product business logic."""
    
    def __init__(self):
        super().__init__(repository=ProductRepository())
    
    async def get_by_sku(self, sku: str) -> Product | None:
        """Get product by SKU."""
        return await self.repository.find_by_field("sku", sku)
```

### Available Methods

#### Read Operations

| Method | Description |
|--------|-------------|
| `get(id)` | Get record by ID |
| `get_or_fail(id)` | Get record or raise error |
| `list(skip, limit, order_by, descending)` | List all records |
| `find_by(skip, limit, **filters)` | Find by filters |
| `find_one_by(**filters)` | Find single record |
| `search(query, fields, skip, limit)` | Full-text search |

#### Write Operations

| Method | Description |
|--------|-------------|
| `create(data, emit_event, validate)` | Create with validation & events |
| `update(id, data, emit_event, validate)` | Update with validation & events |
| `delete(id, emit_event)` | Hard delete |
| `soft_delete(id, emit_event)` | Soft delete |
| `restore(id, emit_event)` | Restore soft-deleted |
| `bulk_create(data_list, emit_event)` | Create multiple records |

#### Count Operations

| Method | Description |
|--------|-------------|
| `count(**filters)` | Count matching records |
| `exists(id)` | Check existence |
| `exists_by(**filters)` | Check existence by filters |
| `paginate(page, per_page, **filters)` | Get paginated results |

### Validation Hooks

Override these methods to add validation:

```python
class ProductService(BaseService[Product, ProductRepository]):
    
    async def validate_create(self, data: dict) -> None:
        """Validate before creation."""
        if await self.repository.exists_by(sku=data.get('sku')):
            raise ValueError("Product with this SKU already exists")
        
        if data.get('price', 0) < 0:
            raise ValueError("Price cannot be negative")
    
    async def validate_update(self, instance: Product, data: dict) -> None:
        """Validate before update."""
        if 'price' in data and data['price'] < 0:
            raise ValueError("Price cannot be negative")
```

### Lifecycle Hooks

Override these methods for custom behavior:

```python
class ProductService(BaseService[Product, ProductRepository]):
    
    async def before_create(self, data: dict) -> dict:
        """Modify data before creation."""
        # Add default values
        if 'status' not in data:
            data['status'] = 'draft'
        return data
    
    async def after_create(self, instance: Product) -> None:
        """Execute after creation."""
        # Log creation, send notifications, etc.
        await send_notification(f"Product {instance.name} created")
    
    async def before_update(self, instance: Product, data: dict) -> dict:
        """Modify update data."""
        # Prevent certain fields from being updated
        data.pop('created_at', None)
        data.pop('created_by_id', None)
        return data
    
    async def after_update(self, old: Product, new: Product) -> None:
        """Execute after update."""
        # Track changes
        if old.price != new.price:
            await log_price_change(old.id, old.price, new.price)
    
    async def before_delete(self, instance: Product) -> None:
        """Execute before deletion."""
        # Check dependencies
        if await self.has_active_orders(instance.id):
            raise ValueError("Cannot delete product with active orders")
    
    async def after_deleted(self, instance: Product) -> None:
        """Execute after deletion."""
        await cleanup_related_data(instance.id)
```

### Event Emission

Services automatically emit events:

```python
from swx_core.events import EventBus

# Listen for events
@EventBus.on("product.created")
async def on_product_created(event):
    product = event.payload['data']
    await send_welcome_email(product)
    await update_search_index(product)

# Events emitted:
# - {model}.created
# - {model}.updated
# - {model}.deleted
# - {model}.soft_deleted
# - {model}.restored
# - {model}.bulk_created
# - {model}.bulk_updated
# - {model}.bulk_deleted
```

---

## BaseController

The `BaseController` provides automatic CRUD endpoints.

### Import

```python
from swx_core.controllers.base import BaseController
```

### Basic Usage

```python
from swx_core.controllers.base import BaseController
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic
from swx_app.services.product_service import ProductService
from swx_app.repositories.product_repository import ProductRepository

class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    """Controller for Product endpoints."""
    
    def __init__(self):
        repository = ProductRepository()
        service = ProductService(repository)
        
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
            tags=["Products"],
            service=service,
            repository=repository,
        )
        
        self.register_routes()
    
    def register_routes(self):
        """Register custom routes."""
        @self.router.get("/search")
        async def search_products(
            q: str = Query(..., min_length=1),
            skip: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
        ):
            """Search products by name or description."""
            return await self.search(q, ["name", "description"], skip, limit)
        
        @self.router.get("/by-sku/{sku}")
        async def get_by_sku(sku: str):
            """Get product by SKU."""
            return await self.get_by("sku", sku)
```

### Automatic CRUD Routes

Use `register_crud_routes()` to auto-generate endpoints:

```python
class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
            tags=["Products"],
        )
        
        # Register standard CRUD routes
        self.register_crud_routes(
            include_list=True,      # GET /products
            include_get=True,        # GET /products/{id}
            include_create=True,     # POST /products
            include_update=True,     # PUT /products/{id}
            include_delete=True,     # DELETE /products/{id}
            include_search=False,    # GET /products/search
        )

# Generated routes:
# GET    /products         → list()
# GET    /products/{id}    → get()
# POST   /products         → create()
# PUT    /products/{id}    → update()
# DELETE /products/{id}    → delete()
```

### Available Methods

#### Read Operations

| Method | Description |
|--------|-------------|
| `list(skip, limit, order_by, descending)` | List all with pagination |
| `get(id)` | Get single record by ID |
| `get_by(field, value)` | Get single record by field |
| `search(query, fields, skip, limit)` | Full-text search |

#### Write Operations

| Method | Description |
|--------|-------------|
| `create(data, created_by_id, emit_event)` | Create new record |
| `update(id, data, emit_event)` | Update record |
| `delete(id, soft_delete, emit_event)` | Delete record |
| `restore(id, emit_event)` | Restore soft-deleted |

#### Bulk Operations

| Method | Description |
|--------|-------------|
| `bulk_create(data_list, created_by_id)` | Create multiple records |
| `bulk_update(ids, data)` | Update multiple records |
| `bulk_delete(ids, soft_delete)` | Delete multiple records |

#### Count Operations

| Method | Description |
|--------|-------------|
| `count(**filters)` | Count matching records |
| `exists(id)` | Check existence |

#### Permission Helpers

| Method | Description |
|--------|-------------|
| `check_permission(user, permission)` | Check if user has permission |
| `require_permission(user, permission)` | Require permission or raise 403 |
| `check_ownership(user, item)` | Check if user owns item |

---

## Quick Start

### Step 1: Create Model

```python
# swx_app/models/product.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from uuid import UUID, uuid4
from datetime import datetime

class ProductBase(SQLModel):
    name: str = Field(max_length=255)
    sku: str = Field(max_length=50, unique=True)
    price: float = Field(gt=0)
    description: str | None = None
    is_active: bool = Field(default=True)

class Product(ProductBase, Base, table=True):
    __tablename__ = "products"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(SQLModel):
    name: str | None = None
    price: float | None = None
    description: str | None = None
    is_active: bool | None = None

class ProductPublic(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

### Step 2: Create Repository

```python
# swx_app/repositories/product_repository.py
from swx_core.repositories.base import BaseRepository
from swx_app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)
```

### Step 3: Create Service

```python
# swx_app/services/product_service.py
from swx_core.services.base import BaseService
from swx_app.repositories.product_repository import ProductRepository
from swx_app.models.product import Product

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())
    
    async def validate_create(self, data: dict) -> None:
        if await self.repository.exists_by(sku=data.get('sku')):
            raise ValueError("SKU already exists")
```

### Step 4: Create Controller

```python
# swx_app/controllers/product_controller.py
from swx_core.controllers.base import BaseController
from swx_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic
from swx_app.services.product_service import ProductService
from swx_app.repositories.product_repository import ProductRepository

class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
            tags=["Products"],
        )
        self.register_routes()
```

### Step 5: Register Routes

```python
# swx_app/routes/v1/product_route.py
from fastapi import APIRouter
from swx_app.controllers.product_controller import ProductController

router = APIRouter()
controller = ProductController()

# Include controller router
router.include_router(controller.router)
```

---

## Complete Example

### Full-Featured Resource

```python
# models/order.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from uuid import UUID, uuid4
from datetime import datetime

class OrderBase(SQLModel):
    user_id: UUID = Field(foreign_key="users.id")
    total: float = Field(gt=0)
    status: str = Field(default="pending")
    shipping_address: str

class Order(OrderBase, Base, table=True):
    __tablename__ = "orders"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)
    
    # Relationships
    # items: list["OrderItem"] = Relationship()

class OrderCreate(SQLModel):
    user_id: UUID
    shipping_address: str
    items: list["OrderItemCreate"]

class OrderUpdate(SQLModel):
    status: str | None = None
    shipping_address: str | None = None

class OrderPublic(OrderBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# repositories/order_repository.py
from swx_core.repositories.base import BaseRepository
from swx_app.models.order import Order

class OrderRepository(BaseRepository[Order]):
    def __init__(self):
        super().__init__(model=Order)
    
    async def find_by_user(self, user_id: UUID, **kwargs) -> list[Order]:
        return await self.find_by(user_id=user_id, **kwargs)

# services/order_service.py
from swx_core.services.base import BaseService
from swx_app.repositories.order_repository import OrderRepository
from swx_app.models.order import Order

class OrderService(BaseService[Order, OrderRepository]):
    def __init__(self):
        super().__init__(repository=OrderRepository())
    
    async def validate_create(self, data: dict) -> None:
        if data.get('total', 0) <= 0:
            raise ValueError("Order total must be positive")
    
    async def before_create(self, data: dict) -> dict:
        data['status'] = 'pending'
        data['order_number'] = await self.generate_order_number()
        return data
    
    async def after_create(self, instance: Order) -> None:
        await self.notify_user(instance.user_id, f"Order {instance.order_number} created")
    
    async def generate_order_number(self) -> str:
        count = await self.repository.count()
        return f"ORD-{count + 1:06d}"

# controllers/order_controller.py
from swx_core.controllers.base import BaseController
from swx_app.models.order import Order, OrderCreate, OrderUpdate, OrderPublic
from swx_app.services.order_service import OrderService
from swx_app.repositories.order_repository import OrderRepository

class OrderController(BaseController[Order, OrderCreate, OrderUpdate, OrderPublic]):
    def __init__(self):
        super().__init__(
            model=Order,
            schema_public=OrderPublic,
            schema_create=OrderCreate,
            schema_update=OrderUpdate,
            prefix="/orders",
            tags=["Orders"],
        )
        self.register_routes()
    
    def register_routes(self):
        @self.router.get("/user/{user_id}")
        async def get_user_orders(
            user_id: UUID,
            skip: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
        ):
            """Get all orders for a user."""
            return await self.service.find_by(user_id=user_id, skip=skip, limit=limit)
        
        @self.router.patch("/{order_id}/complete")
        async def complete_order(order_id: UUID):
            """Mark order as completed."""
            return await self.update(order_id, {"status": "completed"})
```

---

## Best Practices

### Do's

```python
# ✅ Use type hints
class ProductService(BaseService[Product, ProductRepository]):
    async def get_by_sku(self, sku: str) -> Product | None:
        return await self.repository.find_one_by(sku=sku)

# ✅ Override validation hooks
async def validate_create(self, data: dict) -> None:
    if await self.repository.exists_by(sku=data.get('sku')):
        raise ValueError("SKU already exists")

# ✅ Use lifecycle hooks for side effects
async def after_create(self, instance: Product) -> None:
    await self.event_bus.emit("inventory.check", {"product_id": str(instance.id)})

# ✅ Keep controllers thin
class ProductController(BaseController[Product, ...]):
    # Delegate to service
    pass

# ✅ Use soft deletes for audit trails
await controller.delete(id, soft_delete=True)
```

### Don'ts

```python
# ❌ Put business logic in repositories
class ProductRepository(BaseRepository[Product]):
    async def calculate_discount(self, product: Product) -> float:
        # Business logic belongs in SERVICE, not repository
        pass

# ❌ Skip event emission
await service.create(data, emit_event=False)  # Only if you really need to

# ❌ Bypass the service layer
@router.post("/products")
async def create_product(data: ProductCreate, session: SessionDep):
    # Don't access repository directly
    product = await repository.create(data)  # ❌
    # Use service instead
    product = await service.create(data)  # ✅

# ❌ Overwrite core methods incorrectly
async def create(self, data: dict) -> Product:
    # Don't forget to emit events
    return await self.repository.create(data)  # ❌
    # Call parent instead
    return await super().create(data)  # ✅
```

---

**Status:** Base classes documented and ready for use.