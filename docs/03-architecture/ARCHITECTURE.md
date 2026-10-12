# SwX-API Architecture

**Version:** 1.0.0  
**Last Updated:** 2026-01-26  
**Updated:** Policy evaluation example with real-world usage

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Module Boundaries](#module-boundaries)
3. [Request Lifecycle](#request-lifecycle)
4. [Data Model](#data-model)
5. [Domain Separation](#domain-separation)
6. [Async Model](#async-model)
7. [Security Architecture](#security-architecture)

---

## High-Level Architecture

SwX-API follows a **layered, modular architecture** with clear separation between framework code (`swx_core/`) and application code (`swx_app/`).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Requests                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Reverse Proxy (Caddy)                      │
│              SSL Termination, Routing                         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    FastAPI Application                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Middleware Stack                          │   │
│  │  • CORS Middleware                                     │   │
│  │  • Logging Middleware                                  │   │
│  │  • Session Middleware                                  │   │
│  │  • Rate Limit Middleware                               │   │
│  │  • Audit Middleware                                    │   │
│  │  • Sentry Middleware (optional)                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                  │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │              Route Layer                                │ │
│  │  • Dynamic Route Loading                                │ │
│  │  • Route Registration                                   │ │
│  │  • OpenAPI Documentation                                │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │                                  │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │           Authentication & Authorization                 │ │
│  │  • Token Validation (JWT)                               │ │
│  │  • Audience Check (Admin/User/System)                    │ │
│  │  • RBAC Permission Check                                 │ │
│  │  • Policy Evaluation (ABAC)                             │ │
│  │  • Billing Entitlement Check                             │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │                                  │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │              Controller Layer                           │ │
│  │  • Request Validation                                    │ │
│  │  • Orchestration                                         │ │
│  │  • Response Formatting                                   │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │                                  │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │              Service Layer                               │ │
│  │  • Business Logic                                       │ │
│  │  • Domain Rules                                         │ │
│  │  • Cross-cutting Concerns                               │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │                                  │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │            Repository Layer                              │ │
│  │  • Data Access                                           │ │
│  │  • Query Building                                        │ │
│  │  • Transaction Management                                │ │
│  └─────────────────────────┬──────────────────────────────┘ │
└────────────────────────────┼─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│                    Data Layer                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │   PostgreSQL         │  │      Redis            │         │
│  │   • Primary DB       │  │  • Caching            │         │
│  │   • TimescaleDB      │  │  • Rate Limiting      │         │
│  │   • SQLModel ORM     │  │  • Sessions           │         │
│  └──────────────────────┘  └──────────────────────┘         │
└───────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│              Background Services                              │
│  • Job Runner (async job processing)                         │
│  • Alert Engine (multi-channel alerting)                     │
│  • Cache Refresh (periodic cache updates)                    │
└───────────────────────────────────────────────────────────────┘
```

---

## Module Boundaries

### Framework Core (`swx_core/`)

The framework core provides reusable, production-ready components:

```
swx_core/
├── auth/                    # Authentication modules
│   ├── admin/               # Admin domain auth
│   ├── user/                # User domain auth
│   └── core/                # Shared JWT utilities
├── cli/                     # CLI commands
├── config/                  # Configuration management
├── controllers/             # Framework controllers
├── database/                # Database setup and utilities
├── email/                   # Email service
├── middleware/             # Middleware components
├── models/                 # Framework models
├── rbac/                    # RBAC system
├── repositories/            # Framework repositories
├── routes/                  # Framework routes
├── security/               # Security utilities
├── services/                # Framework services
│   ├── billing/             # Billing system
│   ├── channels/            # Alert channels
│   ├── job/                 # Job system
│   ├── policy/              # Policy engine
│   └── rate_limit/          # Rate limiting
└── utils/                   # Utility functions
```

### Application Code (`swx_app/`)

Application-specific code extends the framework:

```
swx_app/
├── controllers/            # Application controllers
├── models/                 # Application models
├── repositories/           # Application repositories
├── routes/                 # Application routes
│   └── v1/                 # Versioned routes
└── services/               # Application services
```

### Clear Separation

- **Framework (`swx_core/`):** Reusable, tested, production-ready
- **Application (`swx_app/`):** Business logic, domain-specific

**Rule:** Application code should **never** import from `swx_core/` internals that aren't part of the public API.

---

## Request Lifecycle

Every request follows this lifecycle:

### 1. Request Arrival

```
Client → Reverse Proxy (Caddy) → FastAPI Application
```

### 2. Middleware Stack

Middleware executes **in order** (first registered = first executed):

1. **Session Middleware** - Session management
2. **CORS Middleware** - Cross-origin resource sharing
3. **Logging Middleware** - Request/response logging
4. **Rate Limit Middleware** - Abuse protection
5. **Audit Middleware** - Action logging
6. **Sentry Middleware** - Error tracking (optional)

### 3. Route Resolution

- Dynamic route loading from `swx_core/routes/` and `swx_app/routes/`
- Route matching based on path and method
- OpenAPI documentation generation

### 4. Authentication

**For Protected Routes:**

```python
# User Domain
from swx_core.auth.user.dependencies import UserDep

@router.get("/user/profile")
async def get_profile(user: UserDep):
    # Token validated, user authenticated
    return user
```

**Authentication Flow:**
1. Extract token from `Authorization: Bearer <token>` header
2. Validate JWT signature and expiration
3. Check token audience (Admin/User/System)
4. Extract subject (email) from token
5. Load user from database
6. Validate user is active
7. Inject user into handler

### 5. Authorization

**RBAC Permission Check:**

```python
from swx_core.rbac.dependencies import require_permission

@router.get("/users", dependencies=[Depends(require_permission("user:read"))])
async def list_users():
    # Permission checked, access granted
    ...
```

**Authorization Flow:**
1. Extract user permissions from token scopes or database
2. Check if user has required permission
3. For team-scoped resources, verify team membership
4. Grant or deny access

### 6. Billing Check

**Entitlement Verification:**

```python
from swx_core.services.billing.enforcement import check_entitlement

# Inside service
await check_entitlement(session, user, "feature:advanced_search")
```

**Billing Flow:**
1. Get user's team and plan
2. Check plan entitlements
3. Verify feature access
4. Return 403 if not entitled

### 7. Policy Evaluation

**ABAC Policy Engine:**

```python
from swx_core.services.policy.dependencies import require_policy

@router.delete("/resource/{id}", dependencies=[Depends(require_policy("resource:delete"))])
async def delete_resource(id: str):
    # Policy evaluated, access granted
    ...
```

**Real-world Example - User Profile Access:**
```python
# swx_core/routes/user/user_route.py
@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    request: Request,
    _policy: None = Depends(
        require_policy(
            action="user:read",
            resource_type="user",
            resource_id=user_id,
            resource_owner_id=user_id
        )
    ),
) -> Any:
    """
    Policy ensures user can only read their own profile
    (unless they have admin permissions via policy).
    """
    return await get_user_by_id_service(session, str(user_id), current_user, request)
```

**Policy Flow:**
1. Load applicable policies
2. Evaluate policy conditions (includes environment from settings)
3. Check policy effect (allow/deny)
4. Grant or deny access

### 8. Rate Limiting

**Plan-Based Limits:**

```python
# Automatic via middleware
# Checks Redis for rate limit counters
# Returns 429 if limit exceeded
```

**Rate Limit Flow:**
1. Identify actor (user, team, IP)
2. Get actor's plan and limits
3. Check Redis for current usage
4. Increment counter if under limit
5. Return 429 if limit exceeded

### 9. Handler Execution

**Controller → Service → Repository:**

```python
# Route Handler (Controller)
@router.get("/users")
async def list_users(session: SessionDep, user: UserDep):
    # Controller orchestrates
    users = await user_service.list_users_service(session, user)
    return users

# Service (Business Logic)
async def list_users_service(session, user):
    # Business rules
    if user.team_id:
        return await user_repository.get_team_users(session, user.team_id)
    return await user_repository.get_all_users(session)

# Repository (Data Access)
async def get_team_users(session, team_id):
    # Database query
    stmt = select(User).where(User.team_id == team_id)
    result = await session.execute(stmt)
    return result.scalars().all()
```

### 10. Audit Logging

**Automatic Logging:**

```python
# Middleware logs request
# Service logs business actions
await audit_logger.log_event(
    action="user.list",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="user",
    outcome=AuditOutcome.SUCCESS,
)
```

### 11. Response

**JSON Response:**

```json
{
  "data": [...],
  "count": 10
}
```

**Error Response:**

```json
{
  "error": "Permission denied"
}
```

---

## Data Model

### Core Entities

```
┌─────────────┐
│   User      │
│  (User Domain)│
└──────┬──────┘
       │
       │ 1:N
       │
┌──────▼──────────┐      ┌──────────────┐
│  TeamMember     │──────│    Team      │
│  (Membership)   │ N:1  │  (Tenant)    │
└─────────────────┘      └──────┬───────┘
                                 │
                                 │ 1:N
                                 │
                    ┌────────────▼──────────┐
                    │      Plan             │
                    │  (Billing Plan)      │
                    └────────────┬──────────┘
                                 │
                                 │ 1:N
                                 │
                    ┌────────────▼──────────┐
                    │    Entitlement        │
                    │  (Feature Access)    │
                    └──────────────────────┘

┌─────────────┐
│ AdminUser   │
│(Admin Domain)│
└─────────────┘

┌─────────────┐      ┌──────────────┐
│   Role      │──────│  Permission  │
│             │ N:N  │              │
└──────┬──────┘      └──────────────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│   UserRole      │
│  (Assignment)   │
└─────────────────┘

┌─────────────┐
│   Policy    │
│  (ABAC Rule)│
└─────────────┘

┌─────────────┐
│  AuditLog   │
│  (Immutable)│
└─────────────┘

┌─────────────┐
│    Job      │
│  (Background)│
└─────────────┘
```

### Key Relationships

1. **User → Team → Plan → Entitlement**
   - Users belong to teams
   - Teams have billing plans
   - Plans have feature entitlements

2. **User → UserRole → Role → Permission**
   - Users have roles
   - Roles have permissions
   - Permissions grant access

3. **Actor → AuditLog**
   - All actions are logged
   - Immutable audit trail

---

## Domain Separation

SwX-API enforces **three distinct domains**:

### 1. Admin Domain

**Purpose:** System administration

**Characteristics:**
- Separate `AdminUser` model
- Separate authentication (`/admin/auth/`)
- Token audience: `"admin"`
- Admin-only routes (`/admin/*`)
- Cannot access user domain resources

**Example:**
```python
from swx_core.auth.admin.dependencies import AdminUserDep

@router.get("/admin/users")
async def list_all_users(admin: AdminUserDep):
    # Only admin tokens can access
    ...
```

### 2. User Domain

**Purpose:** Application users

**Characteristics:**
- `User` model
- User authentication (`/auth/`)
- Token audience: `"user"`
- User routes (`/user/*`, `/api/*`)
- Team-based isolation
- Cannot access admin domain resources

**Example:**
```python
from swx_core.auth.user.dependencies import UserDep

@router.get("/user/profile")
async def get_profile(user: UserDep):
    # Only user tokens can access
    ...
```

### 3. System Domain

**Purpose:** Internal system operations

**Characteristics:**
- Background jobs
- CLI commands
- System-to-system communication
- Token audience: `"system"`
- No HTTP routes (internal only)

**Example:**
```python
# Background job
async def process_job(job: Job):
    # System domain operation
    ...
```

### Domain Isolation Guarantees

✅ **Admin tokens cannot access user routes**  
✅ **User tokens cannot access admin routes**  
✅ **System tokens are internal only**  
✅ **Separate models prevent cross-domain access**  
✅ **Audience validation enforces separation**

---

## Async Model

### Async Guarantees

SwX-API is **fully async** using FastAPI's async capabilities:

1. **All route handlers are async:**
   ```python
   @router.get("/users")
   async def list_users():
       ...
   ```

2. **All database operations are async:**
   ```python
   result = await session.execute(stmt)
   ```

3. **All service calls are async:**
   ```python
   users = await user_service.list_users()
   ```

### Blocking Operations

**⚠️ NEVER block the event loop:**

```python
# ❌ BAD - Blocks event loop
import time
time.sleep(5)  # DON'T DO THIS

# ✅ GOOD - Use async sleep
import asyncio
await asyncio.sleep(5)

# ❌ BAD - Synchronous file I/O
with open("file.txt") as f:
    data = f.read()

# ✅ GOOD - Use async file I/O or thread pool
data = await asyncio.to_thread(open("file.txt").read)
```

### Concurrency Model

- **FastAPI uses asyncio** for request handling
- **Multiple requests** handled concurrently
- **Database connections** pooled (SQLAlchemy async)
- **Redis connections** pooled (aioredis)
- **Background jobs** run in separate async tasks

---

## Security Architecture

### Defense in Depth

1. **Network Layer:** Reverse proxy (Caddy) with SSL
2. **Application Layer:** Middleware stack
3. **Authentication:** JWT with audience validation
4. **Authorization:** RBAC + ABAC policies
5. **Billing:** Entitlement checks
6. **Rate Limiting:** Abuse protection
7. **Audit Logging:** Complete accountability

### Security Boundaries

```
┌─────────────────────────────────────┐
│      Public Internet                │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Reverse Proxy (Caddy)            │
│    • SSL Termination                │
│    • Request Routing                │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    FastAPI Application              │
│    • CORS Protection                │
│    • Rate Limiting                  │
│    • Authentication                 │
│    • Authorization                  │
│    • Audit Logging                  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Database (PostgreSQL)            │
│    • Connection Pooling              │
│    • Query Parameterization         │
│    • Row-Level Security (optional)   │
└─────────────────────────────────────┘
```

### Token Security

- **JWT tokens** with expiration
- **Separate secrets** for each domain
- **Audience validation** prevents cross-domain access
- **Refresh tokens** stored securely in database
- **Token revocation** on password change

### Secrets Management

- **Secrets in .env** (never in database)
- **Runtime settings in database** (non-secret config)
- **Validation guards** prevent secrets in DB
- **Environment separation** (dev/staging/prod)

---

## Next Steps

- Read [Request Lifecycle](../03-architecture/REQUEST_LIFECYCLE.md) for detailed flow
- Read [Core Concepts](../04-core-concepts/) for subsystem details
- Read [Security Model](../05-security/SECURITY_MODEL.md) for security details

---

**Status:** Architecture documented, ready for implementation details.
