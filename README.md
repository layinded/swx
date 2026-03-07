# 🚀 SwX-API

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-🚀-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-success)
![Made with ❤️](https://img.shields.io/badge/Made_with-%E2%9D%A4-red)

**SwX-API** is a **production-ready, enterprise-grade FastAPI framework** designed for building scalable SaaS applications. With comprehensive authentication, authorization, billing, rate limiting, audit logging, and more, it provides everything you need to build and deploy production applications.

> Built with ❤️ for developers who value flexibility, security, and structure.

**🎉 Framework Status: Production Ready v1.0.0**

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
- ✅ **Connection Pooling** - Optimized database connections

### 📊 Operations & Monitoring
- ✅ **Audit Logging** - Immutable security and business event logs
- ✅ **Alerting System** - Multi-channel alerts (Slack, Email, SMS, Logs)
- ✅ **Health Checks** - Comprehensive health monitoring
- ✅ **Runtime Settings** - Database-backed configuration management
- ✅ **Background Jobs** - Job queue with retry logic and dead-letter queue

### 🛠️ Developer Experience
- ✅ **Modular Architecture** - Clean separation of core and app code
- ✅ **SQLModel ORM** - Type-safe database models
- ✅ **Alembic Migrations** - Database version control
- ✅ **CLI Tools** - `swx` command for scaffolding and automation
- ✅ **Comprehensive Documentation** - 43+ documentation files
- ✅ **Testing Tools** - Unit tests, integration tests, acceptance tests
- ✅ **Docker Ready** - Complete Docker Compose setup

---

## 📁 Project Structure

```
swx-api-latest-backend/
├── swx_core/              # Framework code (reusable)
│   ├── auth/              # Authentication (admin, user, system)
│   ├── cli/               # CLI commands
│   ├── config/            # Configuration
│   ├── database/          # Database setup and utilities
│   ├── middleware/        # Middleware (CORS, logging, rate limiting)
│   ├── models/            # Framework models (User, Role, Permission, etc.)
│   ├── rbac/              # RBAC system
│   ├── routes/            # Framework routes (admin, user, utils)
│   ├── security/          # Security utilities
│   ├── services/          # Framework services (billing, jobs, alerts, etc.)
│   └── utils/             # Utility functions
├── swx_app/               # Application code (your features)
│   ├── controllers/       # Application controllers
│   ├── models/            # Application models
│   ├── repositories/      # Application repositories
│   ├── routes/            # Application routes
│   └── services/          # Application services
├── migrations/            # Alembic migrations
├── docs/                  # Comprehensive documentation
│   ├── 01-overview/       # Framework overview
│   ├── 02-getting-started/# Getting started guide
│   ├── 03-architecture/  # Architecture documentation
│   ├── 04-core-concepts/  # Core concepts (9 subsystems)
│   ├── 05-security/       # Security documentation
│   ├── 06-api-usage/      # API usage guides
│   ├── 07-extending/      # Extension guides
│   ├── 08-operations/     # Operations and deployment
│   ├── 09-testing/        # Testing guides
│   ├── 10-troubleshooting/# Troubleshooting
│   └── 11-reference/      # Reference materials
├── scripts/               # Utility scripts
│   ├── seed_system.py     # System seeding
│   ├── full_user_simulation.py # Acceptance tests
│   └── ...
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

### Core Concepts
- **[Authentication](docs/04-core-concepts/AUTHENTICATION.md)** - Auth flows and token security
- **[RBAC](docs/04-core-concepts/RBAC.md)** - Role-based access control
- **[Policy Engine](docs/04-core-concepts/POLICY_ENGINE.md)** - Attribute-based access control
- **[Billing](docs/04-core-concepts/BILLING.md)** - Billing and entitlements
- **[Rate Limiting](docs/04-core-concepts/RATE_LIMITING.md)** - Abuse protection
- **[Audit Logs](docs/04-core-concepts/AUDIT_LOGS.md)** - Logging system
- **[Alerting](docs/04-core-concepts/ALERTING.md)** - Multi-channel alerts
- **[Background Jobs](docs/04-core-concepts/BACKGROUND_JOBS.md)** - Async job processing
- **[Async Model](docs/04-core-concepts/ASYNC_MODEL.md)** - Performance patterns
- **[Settings](docs/04-core-concepts/SETTINGS.md)** - Runtime configuration

### Security
- **[Security Model](docs/05-security/SECURITY_MODEL.md)** - Overall security architecture
- **[Token Security](docs/05-security/TOKEN_SECURITY.md)** - JWT token security
- **[Secrets Management](docs/05-security/SECRETS_MANAGEMENT.md)** - Secure secrets handling
- **[Security Best Practices](docs/05-security/SECURITY_BEST_PRACTICES.md)** - Security guidelines

### Operations
- **[Operations Guide](docs/08-operations/OPERATIONS.md)** - Day-to-day operations
- **[Deployment Guide](docs/08-operations/DEPLOYMENT.md)** - Production deployment
- **[Monitoring](docs/08-operations/MONITORING.md)** - Monitoring and observability
- **[Production Checklist](docs/08-operations/PRODUCTION_CHECKLIST.md)** - Production readiness

### API Usage
- **[API Usage Guide](docs/06-api-usage/API_USAGE.md)** - General API patterns
- **[API Reference](docs/06-api-usage/API_REFERENCE.md)** - Complete endpoint reference
- **[Error Handling](docs/06-api-usage/ERROR_HANDLING.md)** - Error responses
- **[Pagination & Filtering](docs/06-api-usage/PAGINATION_FILTERING.md)** - Query patterns

### Extending
- **[Extending Guide](docs/07-extending/EXTENDING_SWX.md)** - Extension patterns
- **[Adding Features](docs/07-extending/ADDING_FEATURES.md)** - Feature development
- **[Adding Entitlements](docs/07-extending/ADDING_ENTITLEMENTS.md)** - Billing integration
- **[Adding Policies](docs/07-extending/ADDING_POLICIES.md)** - Policy creation
- **[Custom Models](docs/07-extending/CUSTOM_MODELS.md)** - Model patterns

### Testing
- **[Testing Guide](docs/09-testing/TESTING_GUIDE.md)** - Testing patterns
- **[Seeding & Simulation](docs/09-testing/SEEDING_AND_SIMULATION.md)** - Test data setup
- **[Acceptance Testing](docs/09-testing/ACCEPTANCE_TESTING.md)** - Acceptance tests

### Troubleshooting
- **[Troubleshooting Guide](docs/10-troubleshooting/TROUBLESHOOTING.md)** - Common issues
- **[FAQ](docs/10-troubleshooting/FAQ.md)** - Frequently asked questions
- **[Debugging Guide](docs/10-troubleshooting/DEBUGGING.md)** - Debugging techniques

### Reference
- **[Glossary](docs/11-reference/GLOSSARY.md)** - Terms and definitions
- **[Migration Guide](docs/11-reference/MIGRATION_GUIDE.md)** - Upgrade procedures
- **[Changelog](docs/11-reference/CHANGELOG.md)** - Version history

**📖 See [Documentation Index](docs/DOCUMENTATION_STATUS.md) for complete documentation structure.**

---

## 🛠️ Development

### Development Setup

See **[Development Guide](development.md)** for:
- Local development setup
- Running tests
- Code formatting and linting
- CLI commands
- Hot reloading

### CLI Commands

```bash
# Database migrations
swx db migrate
swx db revision -m "description"

# Code generation
swx make:resource blog

# Code quality
swx format      # Format code
swx lint        # Lint code

# Interactive shell
swx tinker
```

---

## 🚀 Deployment

### Production Deployment

See **[Deployment Guide](deployment.md)** for:
- Docker deployment
- Production configuration
- Environment setup
- Post-deployment steps
- Rollback procedures

### Quick Deploy

```bash
# Production deployment
docker compose -f docker-compose.production.yml up -d --build
```

---

## 🧪 Testing

### Running Tests

```bash
# Unit tests
pytest

# Integration tests
pytest swx_core/tests/

# Acceptance tests
python scripts/full_user_simulation.py
```

### Test Coverage

- ✅ Unit tests for services and controllers
- ✅ Integration tests for routes
- ✅ Acceptance tests for complete workflows
- ✅ State validation for data integrity

---

## 📊 Example Usage

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

### Billing

```python
# Check entitlements
from swx_core.services.billing.entitlement_resolver import EntitlementResolver

resolver = EntitlementResolver(session)
has_access = await resolver.check_entitlement(user, "api_requests")
```

---

## 🤝 Contributing

Contributions are welcome! Please see our contributing guidelines for details.

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
