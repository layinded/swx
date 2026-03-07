# Utilities Reference

**Version:** 2.0.0  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Overview](#overview)
2. [Pagination](#pagination)
3. [Response Utilities](#response-utilities)
4. [Caching](#caching)
5. [Validation](#validation)
6. [Model Mixins](#model-mixins)
7. [Rate Limiting](#rate-limiting)
8. [Query Builder](#query-builder)
9. [Error Handling](#error-handling)
10. [Dependency Injection](#dependency-injection)
11. [Health Checks](#health-checks)
12. [Testing Utilities](#testing-utilities)

---

## Overview

SwX provides comprehensive utilities for common operations:

| Utility | Purpose |
|---------|---------|
| `pagination` | Paginated responses with metadata |
| `response` | Standard API response formats |
| `cache` | In-memory and Redis caching |
| `validators` | Validation decorators and functions |
| `mixins` | Reusable model mixins |
| `rate_limit` | Rate limiting decorators |
| `query` | Query builder utilities |
| `errors` | Custom error classes |
| `dependencies` | FastAPI dependency shortcuts |
| `health` | Health check utilities |
| `testing` | Testing helpers and fixtures |

### Import

```python
# Import all utilities
from swx_core.utils import (
    # Pagination
    PaginationParams, PaginatedResponse,
    # Response
    APIResponse, success, error,
    # Caching
    cached, memoize, RedisCache,
    # Validation
    validate_email, validate_password, validate_required,
    # Model mixins
    TimestampMixin, SoftDeleteMixin, FullModelMixin,
    # Rate limiting
    rate_limit, RateLimiter,
    # Query builder
    QueryBuilder, SortOrder,
    # Errors
    NotFoundError, UnauthorizedError, ValidationError,
    # Dependencies
    inject, get_current_user, require_permissions,
    # Health checks
    HealthChecker, check_database, check_redis,
)
```

---

## Pagination

### PaginationParams

Query parameters for pagination:

```python
from swx_core.utils.pagination import PaginationParams, PaginatedResponse
from fastapi import Query

@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    # Calculate offset
    skip = (page - 1) * per_page
    
    # Get items
    items = await repository.find_all(skip=skip, limit=per_page)
    total = await repository.count()
    
    # Return paginated response
    return PaginatedResponse.create(
        data=items,
        total=total,
        page=page,
        per_page=per_page,
    )
```

### PaginatedResponse

Standard paginated response format:

```python
from swx_core.utils.pagination import PaginatedResponse

# Create paginated response
response = PaginatedResponse.create(
    data=products,
    total=150,
    page=2,
    per_page=20,
)

# Response format:
{
    "data": [...],
    "total": 150,
    "page": 2,
    "per_page": 20,
    "total_pages": 8,
    "has_next": true,
    "has_prev": true,
}

# Access properties
print(response.data)      # List of items
print(response.total)     # Total count
print(response.page)      # Current page
print(response.per_page)  # Items per page
print(response.total_pages)  # Total pages
print(response.has_next)  # Has next page
print(response.has_prev)  # Has previous page
```

### CursorPagination

For large datasets, use cursor-based pagination:

```python
from swx_core.utils.pagination import CursorPaginationParams, CursorPaginatedResponse

@router.get("/feed")
async def get_feed(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    # Get items with cursor
    items, next_cursor = await repository.get_with_cursor(
        cursor=cursor,
        limit=limit,
        order_by="created_at",
    )
    
    return CursorPaginatedResponse.create(
        data=items,
        next_cursor=next_cursor,
        has_more=len(items) == limit,
    )
```

---

## Response Utilities

### APIResponse

Standard API response wrapper:

```python
from swx_core.utils.response import APIResponse, success, error

# Success response
@router.get("/products/{product_id}")
async def get_product(product_id: UUID):
    product = await service.get(product_id)
    return success(data=product, message="Product retrieved successfully")

# Error response
@router.get("/products/{product_id}")
async def get_product(product_id: UUID):
    try:
        product = await service.get(product_id)
        return success(data=product)
    except NotFoundError as e:
        return error(message="Product not found", code=404)

# Response format:
{
    "success": true,
    "data": {...},
    "message": "Product retrieved successfully",
    "code": 200,
}
```

### Response Types

```python
from swx_core.utils.response import (
    APIResponse,        # Generic response
    DataResponse,      # Response with data
    ErrorResponse,      # Error response
    ValidationErrorResponse,  # Validation errors
    SuccessResponse,   # Simple success
    DeleteResponse,     # Delete confirmation
    BatchResponse,      # Bulk operation response
    HealthResponse,     # Health check response
    PagedResponse,      # Paginated response
)

# DataResponse
{
    "success": true,
    "data": {...},
}

# ErrorResponse
{
    "success": false,
    "error": "Not found",
    "code": 404,
}

# ValidationErrorResponse
{
    "success": false,
    "error": "Validation failed",
    "code": 422,
    "details": [
        {"field": "email", "message": "Invalid email format"},
        {"field": "password", "message": "Password too short"},
    ],
}

# BatchResponse
{
    "success": true,
    "total": 10,
    "created": 8,
    "failed": 2,
    "errors": [...],
}
```

### Convenience Functions

```python
from swx_core.utils.response import success, error, validation_error

# Success
return success(data=user, message="User created")

# Error
return error(message="User not found", code=404)

# Validation error
return validation_error(
    errors=[
        {"field": "email", "message": "Invalid email"},
        {"field": "password", "message": "Too short"},
    ]
)
```

---

## Caching

### Memory Cache

In-memory caching for development/single-instance:

```python
from swx_core.utils.cache import MemoryCache

# Create cache
cache = MemoryCache()

# Set value
await cache.set("user:123", user_data, ttl=3600)

# Get value
user = await cache.get("user:123")

# Delete value
await cache.delete("user:123")

# Clear all
await cache.clear()

# Check existence
exists = await cache.exists("user:123")
```

### Redis Cache

Distributed caching for production:

```python
from swx_core.utils.cache import RedisCache, init_redis_cache

# Initialize Redis cache
await init_redis_cache(url="redis://localhost:6379/0")

# Get cache instance
cache = RedisCache()

# Use like memory cache
await cache.set("session:abc", session_data, ttl=1800)
session = await cache.get("session:abc")
```

### Decorators

```python
from swx_core.utils.cache import cached, memoize, cache_result

# @cached - Cache function result
@cached(key="products:all", ttl=300)
async def get_all_products():
    return await repository.find_all()

# @memoize - Cache based on function arguments
@memoize(ttl=600)
async def get_product(product_id: UUID):
    return await repository.find_by_id(product_id)

# Clear cache on update
async def update_product(product_id: UUID, data: dict):
    product = await repository.update(product_id, data)
    await invalidate_cache(f"product:{product_id}")
    return product
```

---

## Validation

### Validation Decorators

```python
from swx_core.utils.validators import (
    validate_model,
    validate_email,
    validate_password,
    validate_phone,
    validate_required,
    validate_unique,
    validate_min_value,
    validate_max_value,
    validate_length,
    validate_regex,
    validate_in,
)

# @validate_model - Validate entire model
@validate_model(schema=UserCreate)
async def create_user(data: dict):
    # data is validated
    return await service.create(data)

# @validate_email - Validate email format
@validate_email("email")
async def set_email(user_id: UUID, email: str):
    # email is valid format
    pass

# @validate_password - Validate password strength
@validate_password("password", min_length=8, require_special=True)
async def change_password(user_id: UUID, password: str):
    # password meets requirements
    pass

# @validate_required - Ensure required fields
@validate_required(["name", "email", "password"])
async def register(data: dict):
    # all fields present and non-empty
    pass

# @validate_unique - Ensure unique value
@validate_unique(repository=UserRepository, field="email")
async def create_user(data: dict):
    # email is unique in database
    pass

# @validate_in - Validate value in list
@validate_in("status", choices=["active", "inactive", "pending"])
async def update_status(user_id: UUID, status: str):
    # status is one of the choices
    pass
```

### Validation Functions

```python
from swx_core.utils.validators import validate_email, ValidationError

# Validate email (throws ValidationError)
try:
    validate_email("user@example.com")  # OK
    validate_email("invalid")  # Raises ValidationError
except ValidationError as e:
    print(e.message)  # "Invalid email format"

# Validate password
is_valid = validate_password("MyP@ssw0rd", min_length=8, require_special=True)

# Validate required
validate_required(data, ["name", "email"])  # Raises if missing

# Validate unique
await validate_unique(repository, field="email", value="test@example.com")
```

---

## Model Mixins

### Available Mixins

```python
from swx_core.utils.mixins import (
    TimestampMixin,     # created_at, updated_at
    SoftDeleteMixin,    # is_deleted, soft_delete(), restore()
    UUIDPrimaryKeyMixin, # id: UUID
    CreatedByMixin,     # created_by_id: UUID
    UpdatedByMixin,     # updated_by_id: UUID
    AuditMixin,         # created_by_id, updated_by_id
    ActiveMixin,        # is_active: bool
    SlugMixin,          # slug: str
    TitleMixin,         # title: str
    DescriptionMixin,   # description: str
    MetadataMixin,      # metadata: dict
    FullModelMixin,     # id, created_at, updated_at, is_deleted
    AuditedModelMixin,  # Full model + audit fields
)
```

### Usage

```python
from sqlmodel import SQLModel, Field
from swx_core.utils.mixins import TimestampMixin, SoftDeleteMixin, UUIDPrimaryKeyMixin
from uuid import UUID

# Basic model with timestamps
class Product(UUIDPrimaryKeyMixin, TimestampMixin, SQLModel, table=True):
    __tablename__ = "products"
    
    name: str = Field(max_length=255)
    price: float = Field(gt=0)

# Model with soft delete
class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "users"
    
    email: str = Field(unique=True)
    name: str = Field(max_length=255)

# Full model with all features
class Article(FullModelMixin, SQLModel, table=True):
    __tablename__ = "articles"
    
    title: str = Field(max_length=255)
    content: str
    author_id: UUID = Field(foreign_key="users.id")

# Audited model (includes created_by, updated_by)
class Order(AuditedModelMixin, SQLModel, table=True):
    __tablename__ = "orders"
    
    total: float = Field(gt=0)
    status: str = Field(default="pending")
```

### Mixin Fields

```python
# TimestampMixin adds:
created_at: datetime = Field(default_factory=datetime.utcnow)
updated_at: datetime = Field(default_factory=datetime.utcnow)

# SoftDeleteMixin adds:
is_deleted: bool = Field(default=False)

# UUIDPrimaryKeyMixin adds:
id: UUID = Field(default_factory=uuid4, primary_key=True)

# CreatedByMixin adds:
created_by_id: UUID | None = Field(default=None, foreign_key="users.id")

# UpdatedByMixin adds:
updated_by_id: UUID | None = Field(default=None, foreign_key="users.id")

# ActiveMixin adds:
is_active: bool = Field(default=True)

# SlugMixin adds:
slug: str = Field(max_length=255, unique=True)

# TitleMixin adds:
title: str = Field(max_length=255)

# DescriptionMixin adds:
description: str | None = Field(default=None)

# MetadataMixin adds:
metadata: dict = Field(default_factory=dict)

# FullModelMixin includes:
# - UUIDPrimaryKeyMixin
# - TimestampMixin
# - SoftDeleteMixin

# AuditedModelMixin includes:
# - FullModelMixin
# - CreatedByMixin
# - UpdatedByMixin
```

---

## Rate Limiting

### RateLimiter Class

```python
from swx_core.utils.rate_limit import RateLimiter, RateLimitExceeded

# Create rate limiter
limiter = RateLimiter(
    requests=100,      # Max requests
    window=60,         # Time window in seconds
    prefix="api",      # Key prefix
)

# Check rate limit
try:
    await limiter.check("user:123")  # Check for user
    # Request allowed
except RateLimitExceeded as e:
    # Rate limit exceeded
    raise HTTPException(status_code=429, detail=str(e))
```

### Decorators

```python
from swx_core.utils.rate_limit import rate_limit, rate_limit_by_ip, rate_limit_by_user

# Rate limit by IP
@rate_limit_by_ip(requests=100, window=60)
@router.get("/api/products")
async def list_products():
    return await service.list()

# Rate limit by user
@rate_limit_by_user(requests=50, window=60)
@router.post("/api/orders")
async def create_order(user: UserDep, data: OrderCreate):
    return await service.create(data)

# Custom rate limit key
@rate_limit(key="api:search", requests=30, window=60)
@router.get("/api/search")
async def search(q: str):
    return await service.search(q)

# Rate limit by API key
from swx_core.utils.rate_limit import rate_limit_by_api_key

@rate_limit_by_api_key(requests=1000, window=3600)
@router.get("/api/v2/products")
async def list_products_v2():
    return await service.list()
```

---

## Query Builder

### Basic Usage

```python
from swx_core.utils.query import QueryBuilder, SortOrder
from swx_app.models.product import Product

# Create query builder
builder = QueryBuilder(Product)

# Build query
query = (
    builder
    .where(Product.is_active == True)
    .where(Product.price > 0)
    .search([Product.name, Product.description], "laptop")
    .order_by(Product.created_at, descending=True)
    .limit(20)
    .build()
)

# Execute
async with get_session() as session:
    result = await session.execute(query)
    products = list(result.scalars().all())
```

### Advanced Usage

```python
from swx_core.utils.query import QueryBuilder
from swx_app.models.order import Order

# Complex query
builder = QueryBuilder(Order)

query = (
    builder
    .where(Order.status.in_(["pending", "processing"]))
    .where(Order.total > 100)
    .where(Order.created_at >= datetime.now() - timedelta(days=30))
    .search([Order.order_number], f"ORD-{order_prefix}")
    .order_by(Order.created_at, descending=True)
    .offset(0)
    .limit(50)
    .build()
)

# With joins
from sqlalchemy.orm import selectinload

query = (
    builder
    .where(Order.user_id == user_id)
    .options(selectinload(Order.items))
    .build()
)

# Count query
count_query = builder.count()
```

### Fluent API

```python
# All methods can be chained
results = await (
    QueryBuilder(Product)
    .where(Product.category == "electronics")
    .where(Product.price.between(100, 1000))
    .search([Product.name, Product.sku], search_query)
    .order_by(Product.created_at, descending=True)
    .paginate(page=1, per_page=20)
    .execute()
)

# Or use individual methods
query = QueryBuilder(Product)
query.where(Product.is_active == True)
query.order_by(Product.created_at, SortOrder.DESC)
query.limit(20)
query.build()
```

---

## Error Handling

### Error Classes

```python
from swx_core.utils.errors import (
    SwXError,           # Base error class
    ValidationError,    # 400 Bad Request
    NotFoundError,      # 404 Not Found
    UnauthorizedError,  # 401 Unauthorized
    ForbiddenError,     # 403 Forbidden
    ConflictError,      # 409 Conflict
    RateLimitError,     # 429 Too Many Requests
    ServiceUnavailableError,  # 503 Service Unavailable
    DatabaseError,      # Database error
    ExternalServiceError,  # External API error
    ConfigurationError,  # Config error
)

# Raise specific errors
async def get_product(product_id: UUID):
    product = await repository.find_by_id(product_id)
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product

async def create_product(data: dict):
    if await repository.exists_by(sku=data['sku']):
        raise ConflictError(f"Product with SKU {data['sku']} already exists")
    return await repository.create(data)

async def update_product(product_id: UUID, data: dict):
    if data.get('price', 0) < 0:
        raise ValidationError("Price cannot be negative")
    return await repository.update(product_id, data)
```

### Convenience Functions

```python
from swx_core.utils.errors import (
    not_found,
    unauthorized,
    forbidden,
    bad_request,
    conflict,
    rate_limited,
    service_unavailable,
)

# Quick error raising
async def check_access(user: User, resource: Resource):
    if not user:
        raise unauthorized("Authentication required")
    
    if not user.is_active:
        raise forbidden("Account is inactive")
    
    if user.rate_limit_exceeded:
        raise rate_limited("Rate limit exceeded. Try again later.")

# Not found shortcut
async def get_required(id: UUID):
    result = await repository.find_by_id(id)
    if not result:
        raise not_found(f"Resource {id} not found")
    return result
```

### Exception Handlers

Register in your FastAPI app:

```python
from fastapi import FastAPI
from swx_core.utils.errors import SwXError, NotFoundError, ValidationError

app = FastAPI()

@app.exception_handler(SwXError)
async def swx_error_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "code": exc.status_code,
        }
    )

@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": exc.message,
            "code": 404,
        }
    )
```

---

## Dependency Injection

### Authentication Dependencies

```python
from swx_core.utils.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_superuser,
    require_roles,
    require_permissions,
    require_ownership,
)

# Get current authenticated user (raises 401 if not authenticated)
@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return user

# Get current user or None (no error if not authenticated)
@router.get("/public-content")
async def get_public_content(user: User | None = Depends(get_current_user_optional)):
    if user:
        # Return personalized content
        return await get_recommended_content(user.id)
    return await get_general_content()

# Require superuser
@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: User = Depends(require_superuser)
):
    await service.delete(user_id)
    return {"success": True}

# Require role
@router.get("/admin/dashboard")
async def admin_dashboard(admin: User = Depends(require_roles("admin"))):
    return await service.get_admin_stats()

# Require roles (multiple)
@router.get("/admin/analytics")
async def analytics(
    user: User = Depends(require_roles("admin", "analyst"))
):
    return await service.get_analytics()

# Require permissions
@router.post("/api/products")
async def create_product(
    data: ProductCreate,
    user: User = Depends(require_permissions("product:create"))
):
    return await service.create(data)

# Require ownership
@router.put("/api/orders/{order_id}")
async def update_order(
    order_id: UUID,
    data: OrderUpdate,
    user: User = Depends(require_ownership)
):
    # Only allows if user owns the resource
    # Custom ownership check required in service
    return await service.update(order_id, data, user.id)
```

### Pagination Dependencies

```python
from swx_core.utils.dependencies import get_pagination_params

@router.get("/products")
async def list_products(
    pagination: PaginationParams = Depends(get_pagination_params)
):
    return await service.list(
        skip=pagination.skip,
        limit=pagination.limit,
    )

# PaginationParams includes:
# - page: int (default 1)
# - per_page: int (default 20)
# - skip: int (calculated)
# - limit: int (alias for per_page)
```

### Request Context Dependencies

```python
from swx_core.utils.dependencies import get_request_id, get_client_ip

@router.post("/api/orders")
async def create_order(
    data: OrderCreate,
    request_id: str = Depends(get_request_id),
    client_ip: str = Depends(get_client_ip),
):
    # Log with request ID
    logger.info(f"[{request_id}] Creating order from {client_ip}")
    
    # Create order with audit trail
    return await service.create(data, request_id=request_id)

# Common Dependencies class
from swx_core.utils.dependencies import CommonDependencies

@router.get("/products")
async def list_products(
    deps: CommonDependencies = Depends()
):
    # deps.user - Current user (optional)
    # deps.pagination - Pagination params
    # deps.request_id - Request ID
    # deps.client_ip - Client IP
    return await service.list(deps.pagination)
```

---

## Health Checks

### HealthChecker

```python
from swx_core.utils.health import HealthChecker, HealthStatus

# Create health checker
health = HealthChecker()

# Add checks
health.add_check("database", check_database)
health.add_check("redis", check_redis)
health.add_check("celery", check_celery)

# Run all checks
@router.get("/health")
async def health_check():
    results = await health.run_all()
    
    # results:
    # {
    #     "status": "healthy" | "degraded" | "unhealthy",
    #     "checks": {
    #         "database": {"status": "pass", "latency_ms": 5},
    #         "redis": {"status": "pass", "latency_ms": 2},
    #         "celery": {"status": "fail", "error": "Connection refused"}
    #     }
    # }
    
    return results
```

### Built-in Checks

```python
from swx_core.utils.health import(
    check_database,
    check_redis,
    check_celery,
    check_external_service,
)

# Check database connection
async def check_database() -> HealthCheckResult:
    async with get_session() as session:
        await session.execute(text("SELECT 1"))
    return HealthCheckResult(status=HealthStatus.PASS)

# Check Redis connection
async def check_redis() -> HealthCheckResult:
    client = await get_redis()
    await client.ping()
    return HealthCheckResult(status=HealthStatus.PASS)

# Check Celery workers
async def check_celery() -> HealthCheckResult:
    from celery import app
    inspect = app.control.inspect()
    stats = await inspect.stats()
    if not stats:
        return HealthCheckResult(
            status=HealthStatus.FAIL,
            message="No Celery workers available"
        )
    return HealthCheckResult(status=HealthStatus.PASS)

# Check external service
async def check_external_service(
    name: str,
    url: str,
    timeout: int = 5
) -> HealthCheckResult:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            if response.status_code == 200:
                return HealthCheckResult(status=HealthStatus.PASS)
            return HealthCheckResult(
                status=HealthStatus.FAIL,
                message=f"Status code: {response.status_code}"
            )
    except Exception as e:
        return HealthCheckResult(
            status=HealthStatus.FAIL,
            message=str(e)
        )
```

### Custom Checks

```python
from swx_core.utils.health import HealthChecker, HealthCheckResult, HealthStatus

# Custom check
async def check_disk_space() -> HealthCheckResult:
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_percent = (free / total) * 100
    
    if free_percent < 10:
        return HealthCheckResult(
            status=HealthStatus.FAIL,
            message=f"Low disk space: {free_percent:.1f}% free"
        )
    elif free_percent < 20:
        return HealthCheckResult(
            status=HealthStatus.WARN,
            message=f"Disk space warning: {free_percent:.1f}% free"
        )
    return HealthCheckResult(status=HealthStatus.PASS)

# Register custom check
health.add_check("disk_space", check_disk_space)
```

---

## Testing Utilities

### TestDatabase

```python
from swx_core.utils.testing import TestDatabase, TestSession

# Setup test database
async def setup_test_db():
    test_db = TestDatabase(url="sqlite+aiosqlite:///:memory:")
    await test_db.create()
    yield test_db
    await test_db.drop()

# Use test session
async def test_create_product():
    async with TestSession() as session:
        product = Product(name="Test", price=10.0)
        session.add(product)
        await session.commit()
        
        assert product.id is not None
```

### TestClientWithDB

```python
from swx_core.utils.testing import TestClientWithDB

# Client with automatic DB setup
@pytest.fixture
def client():
    with TestClientWithDB(app) as client:
        yield client

def test_products(client):
    response = client.get("/api/products")
    assert response.status_code == 200
```

### ModelFactory

```python
from swx_core.utils.testing import ModelFactory
from swx_app.models.product import Product

class ProductFactory(ModelFactory[Product]):
    model = Product
    defaults = {
        "name": "Test Product",
        "price": 10.0,
        "sku": lambda: f"SKU-{uuid4().hex[:8]}",
    }

# Create single product
product = await ProductFactory.create()

# Create multiple products
products = await ProductFactory.create_batch(10)

# Override defaults
product = await ProductFactory.create(
    name="Custom Name",
    price=50.0,
)

# Create without saving to DB
product = ProductFactory.build()
```

### Assertion Helpers

```python
from swx_core.utils.testing import (
    assert_response_status,
    assert_response_json,
    assert_model_equal,
)

# Assert response status
def test_api(client):
    response = client.get("/api/products")
    assert_response_status(response, 200)

# Assert response JSON
def test_api_json(client):
    response = client.get("/api/products/123")
    assert_response_json(response, {
        "id": "123",
        "name": "Product",
    })

# Assert model equality
def test_model():
    expected = Product(id=uuid4(), name="Test")
    actual = await service.get(expected.id)
    assert_model_equal(actual, expected, exclude=["created_at", "updated_at"])
```

### Random Data Generators

```python
from swx_core.utils.testing import random_uuid, random_email, random_string

# Generate random UUID
user_id = random_uuid()

# Generate random email
email = random_email()  # "user_abc123@example.com"

# Generate random string
name = random_string(10)  # "aBcDeFgHiJ"
```

---

**Status:** Utilities documented and ready for use.