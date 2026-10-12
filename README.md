# 🚀 SwX-API

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-🚀-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-success)
![Made with ❤️](https://img.shields.io/badge/Made_with-%E2%9D%A4-red)

**SwX-API** is a **production-ready, enterprise-grade FastAPI framework** designed for building scalable SaaS applications. With comprehensive authentication, authorization, billing, rate limiting, audit logging, and more, it provides everything you need to build and deploy production applications.

> Built with ❤️ for developers who value flexibility, security, and structure.

**🎉 Framework Status: Production Ready v2.0.0**

---

## ✨ Key Features

### 🔐 Security & Authentication
- ✅ **Domain Separation** - Admin, User, and System domains completely isolated
- ✅ **OAuth2 + JWT** - Secure token-based authentication with refresh tokens
- ✅ **Social Login** - Google, Facebook, and other OAuth providers
- ✅ **Token Security** - Audience validation, expiration, and revocation
- ✅ **Secrets Management** - Secure handling of sensitive configuration

### 🛡️ Authorization & Access Control
- ✅ **Permission-First RBAC** - Fine-grained access control with team scoping
- ✅ **Policy Engine (ABAC)** - Attribute-based access control with conditions
- ✅ **Team-Scoped Permissions** - Multi-tenant support with team isolation
- ✅ **Fail-Closed Security** - Deny by default, explicit allow

### 💰 Billing & Entitlements
- ✅ **Feature Registry** - Centralized feature management
- ✅ **Plan Management** - Flexible subscription plans (Free, Pro, Team, Enterprise)
- ✅ **Entitlement Resolution** - Automatic feature access checking
- ✅ **Usage Tracking** - Quota and metered feature tracking
- ✅ **Stripe Integration** - Payment processing support

### ⚡ Performance & Scalability
- ✅ **Async Model** - Full async/await support for high performance
- ✅ **Rate Limiting** - Plan-based rate limits with burst protection
- ✅ **Redis Caching** - In-memory caching for improved performance
- ✅ **Background Jobs** - Asynchronous job processing with retries
- ✅ **Connection Pooling** - Optimized database connections with health checks

### 📊 Operations & Monitoring
- ✅ **Audit Logging** - Immutable security and business event logs
- ✅ **Alerting System** - Multi-channel alerts (Slack, Email, SMS, Logs)
- ✅ **Health Checks** - Comprehensive health monitoring
- ✅ **Runtime Settings** - Database-backed configuration management
- ✅ **Background Jobs** - Job queue with retry logic and dead-letter queue

### 🛠️ Developer Experience
- ✅ **Modular Architecture** - Clean separation of core and app code
- ✅ **Base Classes Pattern** - BaseController, BaseService, BaseRepository for rapid development (v2.0)
- ✅ **SQLModel ORM** - Type-safe database models
- ✅ **Alembic Migrations** - Database version control
- ✅ **CLI Tools** - `swx` command for scaffolding with `--base` flag for modern patterns
- ✅ **Comprehensive Documentation** - 50+ documentation files
- ✅ **Testing Tools** - Unit tests, integration tests, acceptance tests
- ✅ **Docker Ready** - Complete Docker Compose setup

---

## 🆕 What's New in v2.0

### BaseController / BaseService / BaseRepository

**Reduce boilerplate by 80%** with the new base classes pattern:

```python
# v2.0 - Modern pattern (recommended)
from swx_core.controllers.base import BaseController
from swx_core.services.base import BaseService
from swx_core.repositories.base import BaseRepository

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)
    # Automatic: find_by_id, find_all, create, update, delete, search, paginate...

class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())
    # Automatic: get, create, update, delete with events and validation hooks...

class ProductController(BaseController[Product, Create, Update, Public]):
    def __init__(self):
        super().__init__(model=Product, ...)
        self.register_routes()
    # Automatic: GET, POST, PUT, DELETE endpoints...
```

### New Utilities

- **Unit of Work** - Transaction management with automatic commit/rollback
- **Filter Builder** - Fluent query filtering and sorting
- **Caching Decorators** - `@cached`, `@memoize` for Redis operations
- **Rate Limiting** - `@rate_limit_by_ip`, `@rate_limit_by_user`
- **Testing Utilities** - ModelFactory, TestClientWithDB, assertions

### CLI Improvements

```bash
# Generate resources with base classes (recommended)
swx make:resource Product --base

# Generate legacy patterns
swx make:resource Product
```

**See [Migration Guide](docs/07-extending/MIGRATION_GUIDE.md) for upgrading from v1.x.**

---

## 📁 Project Structure

```
swx-api-latest-backend/
├── swx_core/              # Framework code (reusable)
│   ├── auth/              # Authentication (admin, user, system)
│   ├── cli/               # CLI commands
│   ├── config/            # Configuration
│   ├── controllers/       # BaseController (v2.0)
│   ├── services/          # BaseService (v2.0)
│   ├── repositories/      # BaseRepository (v2.0)
│   ├── database/          # Database setup and utilities
│   ├── middleware/        # Middleware (CORS, logging, rate limiting)
│   ├── models/            # Framework models (User, Role, Permission, etc.)
│   ├── rbac/              # RBAC system
│   ├── routes/            # Framework routes (admin, user, utils)
│   ├── security/          # Security utilities
│   ├── services/          # Framework services (billing, jobs, alerts, etc.)
│   └── utils/             # Utility functions (pagination, caching, filters...)
├── swx_app/               # Application code (your features)
│   ├── controllers/       # Application controllers
│   ├── models/            # Application models
│   ├── repositories/      # Application repositories
│   ├── routes/            # Application routes
│   └── services/          # Application services
├── migrations/            # Alembic migrations
├── docs/                  # Comprehensive documentation
│   ├── 04-core-concepts/
│   │   ├── BASE_CLASSES.md      # BaseController/BaseService/BaseRepository (NEW)
│   │   ├── UTILITIES.md         # All utility modules (NEW)
│   │   └── USAGE_EXAMPLES.md    # Complete usage examples (NEW)
│   └── 07-extending/
│       └── MIGRATION_GUIDE.md   # v1.x to v2.0 migration (NEW)
├── scripts/               # Utility scripts
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose (development)
└── docker-compose.production.yml # Docker Compose (production)
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Docker & Docker Compose** (recommended)
- **PostgreSQL 12+**
- **Redis 6+**

### Installation

**Option 1: Docker (Recommended)**

```bash
# Clone repository
git clone <repository-url>
cd swx-api-latest-backend

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
# Then start services
docker compose up --build

# Application will be available at:
# - API: http://localhost:8001/api
# - Docs: http://localhost:8001/docs
# - ReDoc: http://localhost:8001/redoc
```

**Option 2: Local Development**

```bash
# Clone repository
git clone <repository-url>
cd swx-api-latest-backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or using uv (faster)
uv pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start development server
uvicorn swx_core.main:app --reload --host 0.0.0.0 --port 8001
```

### Initial Setup

After starting the application:

1. **Seed System Data:**
   ```bash
   python scripts/seed_system.py
   ```

2. **Verify Installation:**
   ```bash
   curl http://localhost:8001/api/utils/health-check
   ```

3. **Access Documentation:**
   - Swagger UI: http://localhost:8001/docs
   - ReDoc: http://localhost:8001/redoc

---

## 📚 Documentation

SwX-API includes **comprehensive documentation** covering all aspects of the framework:

### Getting Started
- **[Getting Started Guide](docs/02-getting-started/GETTING_STARTED.md)** - Installation and setup
- **[Overview](docs/01-overview/OVERVIEW.md)** - Framework introduction
- **[Architecture](docs/03-architecture/ARCHITECTURE.md)** - System design

### Core Concepts (v2.0)
- **[Base Classes](docs/04-core-concepts/BASE_CLASSES.md)** - Controller/Service/Repository pattern
- **[Utilities](docs/04-core-concepts/UTILITIES.md)** - All utility modules
- **[Usage Examples](docs/04-core-concepts/USAGE_EXAMPLES.md)** - Complete code examples
- **[Authentication](docs/04-core-concepts/AUTHENTICATION.md)** - Auth flows and token security
- **[RBAC](docs/04-core-concepts/RBAC.md)** - Role-based access control
- **[Policy Engine](docs/04-core-concepts/POLICY_ENGINE.md)** - Attribute-based access control
- **[Billing](docs/04-core-concepts/BILLING.md)** - Billing and entitlements
- **[Rate Limiting](docs/04-core-concepts/RATE_LIMITING.md)** - Abuse protection
- **[Audit Logs](docs/04-core-concepts/AUDIT_LOGS.md)** - Logging system
- **[Background Jobs](docs/04-core-concepts/BACKGROUND_JOBS.md)** - Async job processing

### Security
- **[Security Model](docs/05-security/SECURITY_MODEL.md)** - Overall security architecture
- **[Token Security](docs/05-security/TOKEN_SECURITY.md)** - JWT token security
- **[Secrets Management](docs/05-security/SECRETS_MANAGEMENT.md)** - Secure secrets handling

### Extending
- **[Extending Guide](docs/07-extending/EXTENDING_SWX.md)** - Extension patterns
- **[Adding Features](docs/07-extending/ADDING_FEATURES.md)** - Feature development
- **[Migration Guide](docs/07-extending/MIGRATION_GUIDE.md)** - v1.x to v2.0 migration

**📖 See [Documentation Index](docs/DOCUMENTATION_STATUS.md) for complete documentation structure.**

---

## 🛠️ Development

### CLI Commands

```bash
# Generate resources with base classes (v2.0 - recommended)
swx make:resource Product --base

# Generate resources with legacy patterns
swx make:resource Product

# Database migrations
swx db migrate
swx db revision -m "description"

# Code quality
swx format      # Format code
swx lint        # Lint code

# Interactive shell
swx tinker
```

---

## 📊 Example Usage

### Base Classes (v2.0)

```python
# Complete resource in minutes
from swx_core.controllers.base import BaseController
from swx_core.services.base import BaseService
from swx_core.repositories.base import BaseRepository
from swx_core.utils.mixins import FullModelMixin

# Model
class Product(FullModelMixin, table=True):
    name: str
    price: float

# Repository
class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product)

# Service  
class ProductService(BaseService[Product, ProductRepository]):
    def __init__(self):
        super().__init__(repository=ProductRepository())

# Controller
class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic]):
    def __init__(self):
        super().__init__(
            model=Product,
            schema_public=ProductPublic,
            schema_create=ProductCreate,
            schema_update=ProductUpdate,
            prefix="/products",
        )
        self.register_routes()

# Automatic endpoints:
# GET    /products          - List with pagination
# GET    /products/{id}      - Get by ID
# POST   /products          - Create
# PUT    /products/{id}     - Update
# DELETE /products/{id}     - Delete
```

### Authentication

```python
# User domain authentication
from swx_core.security.dependencies import get_current_user

@router.get("/user/profile")
async def get_profile(user: User = Depends(get_current_user)):
    return user
```

### Authorization

```python
# Permission-based access
from swx_core.rbac.dependencies import require_permission

@router.get("/users", dependencies=[Depends(require_permission("user:read"))])
async def list_users():
    ...
```

### Rate Limiting

```python
from swx_core.utils.rate_limit import rate_limit_by_user

@router.get("/api/search")
@rate_limit_by_user(requests=100, window=60)  # 100 req/min
async def search(q: str):
    return await search_service.search(q)
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLModel for the ORM
- All contributors and users

---

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

---

**Built with ❤️ for developers who value flexibility, security, and structure.**