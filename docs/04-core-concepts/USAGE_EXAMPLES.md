# Usage Examples

**Version:** 2.1.0  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Base Classes Examples](#base-classes-examples)
3. [API Development Examples](#api-development-examples)
4. [Authentication Examples](#authentication-examples)
5. [Rate Limiting Examples](#rate-limiting-examples)
6. [Caching Examples](#caching-examples)
7. [Event-Driven Examples](#event-driven-examples)
8. [Background Jobs Examples](#background-jobs-examples)
9. [Full Application Example](#full-application-example)

---

## Quick Start

### Install

```bash
pip install swx-core>=2.0.0
```

### Minimal Application

```python
# main.py
from fastapi import FastAPI
from swx_core.main import app  # Use the pre-configured app

# Or create your own:
from fastapi import FastAPI
from swx_core.config.discovery import DiscoveryConfig

# Configure your app location
discovery = DiscoveryConfig(app_name="my_app", app_base="./my_app")

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Base Classes Examples

### Creating a Complete Resource

```python
# my_app/models/product.py
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base
from swx_core.utils.mixins import FullModelMixin
from uuid import UUID, uuid4
from datetime import datetime

class ProductBase(SQLModel):
    name: str = Field(max_length=255)
    sku: str = Field(max_length=50, unique=True)
    price: float = Field(gt=0)
    description: str | None = None
    is_active: bool = Field(default=True)

class Product(FullModelMixin, ProductBase, table=True):
    """Product model with automatic id, timestamps, and soft delete."""
    __tablename__ = "products"

class ProductCreate(SQLModel):
    name: str
    sku: str
    price: float
    description: str | None = None

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

### Repository with Base Class

```python
# my_app/repositories/product_repository.py
from swx_core.repositories.base import BaseRepository
from my_app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    """Repository for Product with automatic CRUD operations."""
    
    def __init__(self):
        super().__init__(model=Product)
    
    async def find_by_sku(self, sku: str) -> Product | None:
        """Find product by SKU."""
        return await self.find_one_by(sku=sku)
    
    async def find_active(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """Find all active products."""
        return await self.find_by(skip=skip, limit=limit, is_active=True)
    
    async def search_products(self, query: str) -> list[Product]:
        """Full-text search across name and description."""
        return await self.search(query, ["name", "description"])
```

### Service with Business Logic

```python
# my_app/services/product_service.py
from swx_core.services.base import BaseService
from my_app.repositories.product_repository import ProductRepository
from my_app.models.product import Product

class ProductService(BaseService[Product, ProductRepository]):
    """Service for Product business logic with validation."""
    
    def __init__(self):
        super().__init__(repository=ProductRepository())
    
    async def validate_create(self, data: dict) -> None:
        """Validate product creation."""
        # Check if SKU already exists
        if await self.repository.exists_by(sku=data.get('sku')):
            raise ValueError(f"Product with SKU {data['sku']} already exists")
        
        # Validate price
        if data.get('price', 0) <= 0:
            raise ValueError("Price must be greater than 0")
    
    async def validate_update(self, instance: Product, data: dict) -> None:
        """Validate product update."""
        if 'price' in data and data['price'] <= 0:
            raise ValueError("Price must be greater than 0")
    
    async def before_create(self, data: dict) -> dict:
        """Hook called before creation."""
        # Add default values
        if 'is_active' not in data:
            data['is_active'] = True
        return data
    
    async def after_create(self, instance: Product) -> None:
        """Hook called after creation."""
        # Emit event for listeners
        await self.event_bus.emit("product.created", {
            "id": str(instance.id),
            "sku": instance.sku,
            "name": instance.name
        })
    
    async def get_active_products(self, skip: int = 0, limit: int = 100):
        """Get all active products."""
        return await self.repository.find_active(skip=skip, limit=limit)
```

### Controller with Automatic Endpoints

```python
# my_app/controllers/product_controller.py
from swx_core.controllers.base import BaseController
from my_app.models.product import Product, ProductCreate, ProductUpdate, ProductPublic
from my_app.services.product_service import ProductService
from my_app.repositories.product_repository import ProductRepository

class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    """Controller with automatic CRUD endpoints."""
    
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
    
    def register_routes(self):
        """Register custom routes in addition to standard CRUD."""
        
        # Custom search endpoint
        @self.router.get("/search")
        async def search_products(q: str, skip: int = 0, limit: int = 100):
            """Full-text search for products."""
            return await self.search(q, ["name", "description"], skip, limit)
        
        # Get by SKU endpoint
        @self.router.get("/by-sku/{sku}")
        async def get_by_sku(sku: str):
            """Get product by SKU."""
            return await self.get_by("sku", sku)
        
        # Bulk activation endpoint
        @self.router.post("/bulk-activate")
        async def bulk_activate(ids: list[str]):
            """Activate multiple products."""
            return await self.bulk_update(ids, {"is_active": True})

# Create router instance
controller = ProductController()
router = controller.router
```

### Routes with Authentication

```python
# my_app/routes/v1/product_route.py
from fastapi import APIRouter, Depends
from swx_core.auth.user.dependencies import UserDep
from swx_core.rbac.dependencies import require_permission
from my_app.controllers.product_controller import controller

router = APIRouter()

# Include controller routes (automatic CRUD)
router.include_router(controller.router)

# Routes are protected by default with UserDep
# Add RBAC permissions:

@router.get("/", dependencies=[Depends(require_permission("product:read"))])
async def list_products(skip: int = 0, limit: int = 100, user: UserDep = Depends()):
    """List all products with RBAC protection."""
    return await controller.list(skip=skip, limit=limit)

@router.post("/", dependencies=[Depends(require_permission("product:create"))])
async def create_product(data: dict, user: UserDep = Depends()):
    """Create product with permission check."""
    return await controller.create(data, created_by_id=user.id)
```

---

## API Development Examples

### Pagination with Filters

```python
from fastapi import Query
from swx_core.utils.filters import FilterBuilder, SortBuilder
from swx_core.utils.pagination import paginate

@router.get("/products")
async def list_products(
    # Pagination
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    
    # Filters
    name: str | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    is_active: bool | None = Query(None),
    
    # Sorting
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
):
    """List products with pagination, filtering, and sorting."""
    
    # Build filters
    filters = FilterBuilder()
    if name:
        filters.contains(Product.name, name)
    if min_price is not None:
        filters.gte(Product.price, min_price)
    if max_price is not None:
        filters.lte(Product.price, max_price)
    if is_active is not None:
        filters.eq(Product.is_active, is_active)
    
    # Get sort column
    sort_column = getattr(Product, sort_by, Product.created_at)
    
    # Get repository
    repo = ProductRepository()
    
    # Get paginated results
    result = await repo.paginate(
        page=page,
        per_page=per_page,
        order_by=sort_by,
        descending=(sort_order == "desc"),
        **filters.build_conditions()
    )
    
    return result
```

### Error Handling

```python
from swx_core.utils.errors import NotFoundError, ValidationError, ConflictError

@router.post("/products")
async def create_product(data: ProductCreate):
    try:
        product = await product_service.create(data.dict())
        return product
    except ValueError as e:
        raise ValidationError(str(e))
    except Exception as e:
        # Log and re-raise
        logger.error(f"Error creating product: {e}")
        raise

@router.get("/products/{product_id}")
async def get_product(product_id: UUID):
    product = await product_service.get_or_fail(product_id)
    return product
```

---

## Authentication Examples

### JWT Authentication

```python
from fastapi import Depends
from swx_core.auth.user.dependencies import UserDep, get_current_user
from swx_core.utils.dependencies import require_permissions

@router.get("/profile")
async def get_profile(user: UserDep = Depends(get_current_user)):
    """Get current user profile."""
    return {"id": str(user.id), "email": user.email}

@router.get("/admin/users")
async def list_users(user: UserDep = Depends(require_permissions("admin:read"))):
    """List all users (admin only)."""
    return await user_service.list()
```

### Custom Authentication

```python
from swx_core.auth.core.jwt_handler import create_access_token, verify_token

@router.post("/login")
async def login(email: str, password: str):
    user = await auth_service.authenticate(email, password)
    if not user:
        raise UnauthorizedError("Invalid credentials")
    
    token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    return {"access_token": token, "token_type": "bearer"}
```

---

## Rate Limiting Examples

### Basic Rate Limiting

```python
from swx_core.utils.rate_limit import rate_limit_by_ip, rate_limit_by_user

@router.get("/api/public")
@rate_limit_by_ip(requests=100, window=60)  # 100 requests per minute per IP
async def public_endpoint():
    return {"message": "Public data"}

@router.get("/api/user/profile")
@rate_limit_by_user(requests=50, window=60)  # 50 requests per minute per user
async def user_profile(user: UserDep):
    return await user_service.get_profile(user.id)
```

### Custom Rate Limiting

```python
from swx_core.utils.rate_limit import RateLimiter

# Create rate limiter
limiter = RateLimiter(requests=100, window=60, prefix="api")

@router.post("/api/search")
async def search(request: Request, q: str):
    # Check rate limit manually
    client_ip = request.client.host
    try:
        await limiter.check(client_ip)
    except RateLimitExceeded:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return await search_service.search(q)
```

---

## Caching Examples

### Function Caching

```python
from swx_core.utils.cache import cached, memoize, RedisCache

# Cache function result
@cached(key="products:all", ttl=300)  # 5 minutes
async def get_all_products():
    return await product_repository.find_all()

# Cache with arguments
@memoize(ttl=600)  # 10 minutes
async def get_product(product_id: UUID):
    return await product_repository.find_by_id(product_id)

# Invalidate cache on update
async def update_product(product_id: UUID, data: dict):
    product = await product_repository.update(product_id, data)
    await cache.delete(f"product:{product_id}")
    return product
```

### Redis Cache

```python
from swx_core.utils.cache import RedisCache, init_redis_cache

# Initialize Redis cache
await init_redis_cache(url="redis://localhost:6379/0")

# Use Redis for session storage
cache = RedisCache()
await cache.set("session:abc123", {"user_id": "123"}, ttl=3600)
session = await cache.get("session:abc123")
```

---

## Event-Driven Examples

### Define Events

```python
# my_app/events.py
from swx_core.events import EventBus

# Subscribe to events
@EventBus.on("product.created")
async def on_product_created(event):
    """Handle product creation event."""
    product_id = event.payload["id"]
    # Send notification
    await notification_service.send(f"Product {product_id} created")
    # Update search index
    await search_service.index_product(product_id)

@EventBus.on("product.updated")
async def on_product_updated(event):
    """Handle product update event."""
    product_id = event.payload["id"]
    await search_service.reindex_product(product_id)

@EventBus.on("product.deleted")
async def on_product_deleted(event):
    """Handle product deletion event."""
    product_id = event.payload["id"]
    await search_service.remove_product(product_id)
```

### Emit Events

```python
from swx_core.events import EventBus

# Events are automatically emitted by BaseService
# But you can emit custom events:

async def custom_operation(product_id: UUID):
    # Do something
    result = await do_something(product_id)
    
    # Emit custom event
    await EventBus.emit("product.custom_operation", {
        "product_id": str(product_id),
        "result": result
    })
    
    return result
```

---

## Background Jobs Examples

### Define Jobs

```python
# my_app/workers/email_worker.py
from swx_core.services.job import CeleryJob, register_handler
from my_app.services.email_service import EmailService

@register_handler("send_email")
async def send_email_handler(job: CeleryJob):
    """Handle email sending job."""
    data = job.payload
    await EmailService.send(
        to=data["to"],
        subject=data["subject"],
        body=data["body"]
    )

# my_app/workers/report_worker.py
@register_handler("generate_report")
async def generate_report_handler(job: CeleryJob):
    """Handle report generation job."""
    report_type = job.payload["report_type"]
    user_id = job.payload["user_id"]
    
    report = await report_service.generate(report_type)
    
    # Notify user
    await notification_service.notify(user_id, f"Report {report_type} ready")
```

### Queue Jobs

```python
from swx_core.services.job import JobQueue

# Queue a job
await JobQueue.enqueue("send_email", {
    "to": "user@example.com",
    "subject": "Welcome",
    "body": "Welcome to our platform!"
})

# Schedule a job
await JobQueue.schedule(
    "generate_report",
    {"report_type": "monthly", "user_id": str(user.id)},
    run_at=datetime.now() + timedelta(hours=1)
)
```

---

## Full Application Example

### Project Structure

```
my_app/
├── __init__.py
├── main.py
├── models/
│   ├── __init__.py
│   ├── product.py
│   └── user.py
├── repositories/
│   ├── __init__.py
│   ├── product_repository.py
│   └── user_repository.py
├── services/
│   ├── __init__.py
│   ├── product_service.py
│   └── user_service.py
├── controllers/
│   ├── __init__.py
│   ├── product_controller.py
│   └── user_controller.py
├── routes/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── product_route.py
│       └── user_route.py
├── events/
│   ├── __init__.py
│   └── handlers.py
└── workers/
    ├── __init__.py
    └── email_worker.py
```

### Main Application

```python
# my_app/main.py
from fastapi import FastAPI
from swx_core.config.discovery import DiscoveryConfig
from swx_core.main import app  # Use the pre-configured app

# Or create custom:
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    version="1.0.0"
)

# Configure app discovery
discovery = DiscoveryConfig(app_name="my_app")

# Routes are auto-discovered from my_app/routes/v1/
# Models are auto-loaded from my_app/models/
# Services are auto-loaded from my_app/services/

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Running with Docker

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
  
  worker:
    build: .
    command: celery -A swx_core.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: myapp
  
  redis:
    image: redis:7
```

---

**Status:** Usage examples documented and ready for use.