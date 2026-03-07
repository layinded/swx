# SwX-API Overview

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## What is SwX-API?

**SwX-API** is a production-ready, enterprise-grade **FastAPI framework** designed for building scalable, secure, multi-tenant SaaS applications. It provides a complete foundation with authentication, authorization, billing, rate limiting, audit logging, alerting, and background job processing.

SwX-API is **not** a generic web framework—it's a **specialized framework** for building SaaS backends with:

- **Multi-tenant architecture** with team-based isolation
- **Permission-first RBAC** with fine-grained access control
- **Domain separation** (Admin, User, System) for security
- **Billing and entitlements** system with Stripe integration
- **Policy engine** (ABAC) for flexible access control
- **Production-grade features** (audit logs, alerts, rate limiting, jobs)

---

## What Problems Does SwX-API Solve?

### 1. **Rapid SaaS Backend Development**

**Problem:** Building a SaaS backend from scratch requires implementing:
- Multi-tenant data isolation
- Authentication and authorization
- Billing and subscription management
- Rate limiting and abuse protection
- Audit logging and compliance
- Background job processing
- Alerting and monitoring

**Solution:** SwX-API provides all of these as **integrated, production-ready components** that work together out of the box.

### 2. **Security and Compliance**

**Problem:** SaaS applications need:
- Fine-grained access control (RBAC + ABAC)
- Complete audit trails for compliance
- Secure token handling with audience validation
- Domain isolation (admin vs user)
- Secrets management

**Solution:** SwX-API enforces:
- **Permission-first RBAC** with team scoping
- **ABAC policy engine** for flexible rules
- **Complete audit logging** of all actions
- **Domain separation** (Admin, User, System)
- **Secure token handling** with audience validation

### 3. **Multi-Tenancy and Team Isolation**

**Problem:** SaaS applications need:
- Team-based data isolation
- Team-scoped permissions and roles
- Team billing and entitlements
- Team member management

**Solution:** SwX-API provides:
- **Team model** with automatic isolation
- **Team-scoped roles** and permissions
- **Team billing** with plan management
- **Team member** management with role assignment

### 4. **Billing and Entitlements**

**Problem:** SaaS applications need:
- Subscription management
- Plan-based feature access
- Usage tracking
- Payment provider integration

**Solution:** SwX-API includes:
- **Billing domain** with Plans, Features, Entitlements
- **Stripe integration** (extensible to other providers)
- **Entitlement resolver** for feature access checks
- **Usage tracking** and billing enforcement

### 5. **Operational Excellence**

**Problem:** Production applications need:
- Rate limiting to prevent abuse
- Background job processing
- Alerting for critical events
- Audit logs for debugging and compliance
- Runtime configuration without redeployment

**Solution:** SwX-API provides:
- **Rate limiting** with plan-based limits
- **Background job system** with retries and idempotency
- **Alert engine** with multiple channels (Slack, Email, SMS, Logs)
- **Audit logging** with immutable records
- **Runtime settings** system (DB-backed configuration)

---

## What SwX-API Is NOT

### ❌ Not a Generic Web Framework

SwX-API is **not** designed for:
- Simple CRUD applications
- Static websites
- Microservices without multi-tenancy
- Applications without billing needs

### ❌ Not a CMS or Content Platform

SwX-API does **not** provide:
- Content management features
- Media handling
- Rich text editing
- Content workflows

### ❌ Not a Low-Code Platform

SwX-API is **not**:
- A visual builder
- A no-code solution
- A drag-and-drop interface builder

### ❌ Not a Complete Application

SwX-API is a **framework**, not a complete application. You must:
- Define your business models
- Implement your business logic
- Build your frontend
- Configure your infrastructure

---

## Intended Audience

### ✅ Perfect For

1. **SaaS Startups**
   - Need rapid backend development
   - Require multi-tenancy
   - Need billing integration
   - Want production-grade security

2. **Enterprise Teams**
   - Building internal SaaS tools
   - Need compliance and audit trails
   - Require fine-grained access control
   - Want operational excellence

3. **Platform Engineers**
   - Building developer platforms
   - Need team-based isolation
   - Require policy-based access
   - Want extensible architecture

4. **Full-Stack Developers**
   - Building SaaS products
   - Want to focus on business logic
   - Need production-ready infrastructure
   - Prefer Python/FastAPI

### ❌ Not Ideal For

1. **Simple CRUD Applications**
   - Overkill for basic applications
   - Unnecessary complexity

2. **Non-Multi-Tenant Applications**
   - Framework assumes multi-tenancy
   - Single-tenant apps don't benefit

3. **Teams Without Python Expertise**
   - Framework is Python/FastAPI
   - Requires Python knowledge

4. **Applications Without Billing Needs**
   - Billing system is core to framework
   - Unused complexity if not needed

---

## Design Philosophy

### 1. **Security First**

- **Domain separation** prevents cross-domain access
- **Permission-first RBAC** ensures explicit access control
- **Audit logging** provides complete accountability
- **Policy engine** enables flexible security rules
- **Token security** with audience validation

### 2. **Production Ready**

- **Rate limiting** prevents abuse
- **Background jobs** handle async work
- **Alerting** for critical events
- **Error handling** with proper logging
- **Monitoring hooks** for observability

### 3. **Developer Experience**

- **Clear module boundaries** (core vs app)
- **Type safety** with SQLModel and Pydantic
- **Comprehensive testing** tools
- **CLI tools** for scaffolding
- **Complete documentation**

### 4. **Extensibility**

- **Plugin architecture** for features
- **Policy engine** for custom rules
- **Alert channels** for custom integrations
- **Billing providers** for payment systems
- **Job handlers** for custom workflows

### 5. **Operational Excellence**

- **Idempotent seeding** for safe initialization
- **Full simulation** for acceptance testing
- **Runtime settings** for configuration changes
- **Audit trails** for debugging
- **Structured logging** for observability

---

## Key Features

### Authentication & Authorization

- **OAuth2 + JWT** authentication
- **Social login** (Google, Facebook, GitHub)
- **Refresh tokens** with secure storage
- **Permission-first RBAC** with team scoping
- **ABAC policy engine** for flexible rules
- **Domain separation** (Admin, User, System)

### Billing & Entitlements

- **Plans and tiers** (Free, Pro, Enterprise)
- **Feature-based entitlements**
- **Stripe integration** (extensible)
- **Usage tracking**
- **Billing enforcement**

### Rate Limiting

- **Plan-based limits** (Free, Pro, Enterprise)
- **Burst and sustained** limits
- **Skip paths** for critical endpoints
- **Abuse detection**
- **Redis-backed** for scalability

### Audit Logging

- **Complete audit trail** of all actions
- **Immutable records** for compliance
- **Actor tracking** (who did what)
- **Resource tracking** (what was affected)
- **Outcome tracking** (success/failure)

### Alerting

- **Multi-channel** (Slack, Email, SMS, Logs)
- **Severity levels** (INFO, WARNING, ERROR, CRITICAL)
- **Routing rules** for channel selection
- **Failure handling** with retries
- **Alert aggregation**

### Background Jobs

- **Async job processing**
- **Retry logic** with exponential backoff
- **Idempotency** guarantees
- **Job status tracking**
- **Handler registration**

### Runtime Settings

- **Database-backed** configuration
- **Type-safe** settings access
- **Cache invalidation** on updates
- **Audit logging** of changes
- **Validation guards** for safety

---

## Architecture Overview

SwX-API follows a **layered architecture**:

```
┌─────────────────────────────────────┐
│         API Routes Layer            │
│  (FastAPI endpoints, validation)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Controller Layer              │
│  (Request handling, orchestration)  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Service Layer                │
│  (Business logic, domain rules)       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Repository Layer                │
│  (Data access, queries)               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Database Layer                │
│  (PostgreSQL, SQLModel)              │
└──────────────────────────────────────┘
```

### Request Flow

1. **Request arrives** → Middleware (CORS, logging, rate limiting)
2. **Authentication** → Token validation, audience check
3. **Authorization** → RBAC permission check
4. **Billing check** → Entitlement verification
5. **Policy evaluation** → ABAC policy engine
6. **Rate limiting** → Plan-based limits
7. **Handler execution** → Controller → Service → Repository
8. **Audit logging** → Action logged
9. **Response** → JSON response with proper status

---

## Technology Stack

### Core

- **Python 3.10+** - Programming language
- **FastAPI** - Web framework
- **SQLModel** - ORM (SQLAlchemy + Pydantic)
- **PostgreSQL** - Primary database
- **Alembic** - Database migrations

### Infrastructure

- **Redis** - Caching and rate limiting
- **Docker** - Containerization
- **Caddy** - Reverse proxy
- **TimescaleDB** - Time-series data (optional)

### Authentication

- **JWT** - Token-based auth
- **OAuth2** - Standard auth flow
- **bcrypt** - Password hashing

### Billing

- **Stripe** - Payment processing (extensible)

### Monitoring

- **Sentry** - Error tracking (optional)
- **Structured logging** - JSON logs

---

## Getting Started

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd swx-api-latest-backend

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Start with Docker
docker-compose up --build

# Or run locally
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn swx_core.main:app --reload
```

### Next Steps

1. **Read [Getting Started Guide](../02-getting-started/GETTING_STARTED.md)**
2. **Review [Architecture Documentation](../03-architecture/ARCHITECTURE.md)**
3. **Explore [Core Concepts](../04-core-concepts/)**
4. **Check [API Usage Guide](../06-api-usage/API_USAGE.md)**

---

## Framework Status

**Version:** 1.0.0  
**Status:** Production Ready ✅

### Completed Features

- ✅ Permission-first RBAC system
- ✅ Domain separation (Admin, User, System)
- ✅ Multi-tenant team isolation
- ✅ Billing and entitlements
- ✅ Policy engine (ABAC)
- ✅ Rate limiting
- ✅ Audit logging
- ✅ Alerting system
- ✅ Background jobs
- ✅ Runtime settings
- ✅ Full user simulation
- ✅ Comprehensive testing

### Production Readiness

- ✅ Security hardened
- ✅ Error handling
- ✅ Logging and monitoring
- ✅ Docker support
- ✅ Migration system
- ✅ Documentation

---

## Support and Community

### Documentation

- **Framework Guide** - Comprehensive usage guide
- **API Reference** - Complete API documentation
- **Architecture Docs** - System design documentation
- **Troubleshooting** - Common issues and solutions

### Resources

- **GitHub Repository** - Source code and issues
- **Examples** - Sample implementations
- **Tests** - Test suite and examples

---

## License

See [LICENSE](../../LICENSE) file for details.

---

## Conclusion

SwX-API is a **production-ready framework** for building SaaS backends. It provides:

- **Security** through RBAC, policies, and audit logs
- **Scalability** through async architecture and rate limiting
- **Operational excellence** through jobs, alerts, and monitoring
- **Developer experience** through clear structure and documentation

If you're building a SaaS application that needs multi-tenancy, billing, and production-grade features, SwX-API provides a solid foundation to build upon.

**Next:** Read the [Getting Started Guide](../02-getting-started/GETTING_STARTED.md) to set up your development environment.
