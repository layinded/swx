# Security Model

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Security Domains](#security-domains)
3. [Domain Separation](#domain-separation)
4. [Authentication Model](#authentication-model)
5. [Authorization Model](#authorization-model)
6. [Defense in Depth](#defense-in-depth)
7. [Security Guarantees](#security-guarantees)
8. [Threat Model](#threat-model)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API implements a **multi-layered security model** with strict domain separation, comprehensive authentication, and defense-in-depth principles. Security is built into every layer of the framework.

### Key Principles

1. **Domain Separation** - Admin, User, and System domains are completely isolated
2. **Fail-Closed** - Security failures deny access by default
3. **Least Privilege** - Users have minimum necessary permissions
4. **Defense in Depth** - Multiple security layers protect resources
5. **Audit Everything** - All security events are logged
6. **No Secrets in Code** - Secrets stored in environment variables

---

## Security Domains

### Three Distinct Domains

SwX-API enforces **three completely separate security domains**:

#### 1. Admin Domain

**Purpose:** System administration and management

**Characteristics:**
- Separate `AdminUser` model
- Separate authentication endpoints (`/api/admin/auth`)
- Separate token audience (`"admin"`)
- Separate secret key (optional, can use same as user)
- Admin-only routes (`/api/admin/*`)

**Use Cases:**
- System configuration
- User management
- Billing management
- Audit log access
- Settings management

**Security:**
- Highest privilege level
- Access to all resources
- Separate token validation
- Cannot access user endpoints

#### 2. User Domain

**Purpose:** Regular application users

**Characteristics:**
- Separate `User` model
- Separate authentication endpoints (`/api/auth`)
- Separate token audience (`"user"`)
- Separate secret key (optional, can use same as admin)
- User routes (`/api/user/*`)

**Use Cases:**
- User profile management
- Team membership
- Resource access (scoped by permissions)
- Billing account access

**Security:**
- Permission-based access
- Team-scoped resources
- Policy engine evaluation
- Cannot access admin endpoints

#### 3. System Domain

**Purpose:** Internal system operations

**Characteristics:**
- No user model (system operations)
- System token audience (`"system"`)
- Separate secret key (optional)
- Background jobs, CLI commands

**Use Cases:**
- Background job execution
- CLI operations
- System maintenance
- Automated tasks

**Security:**
- Highest privilege (system-level)
- No user context
- Limited to system operations
- Not exposed via API

---

## Domain Separation

### Complete Isolation

**Domains are completely isolated:**

1. **Separate Models**
   ```python
   # Admin domain
   AdminUser  # Separate model
   
   # User domain
   User  # Separate model
   
   # System domain
   # No model (system operations)
   ```

2. **Separate Authentication**
   ```python
   # Admin domain
   POST /api/admin/auth  # Admin login
   
   # User domain
   POST /api/auth  # User login
   
   # System domain
   # No API endpoint (internal only)
   ```

3. **Separate Token Audiences**
   ```python
   # Admin domain
   TokenAudience.ADMIN  # "admin"
   
   # User domain
   TokenAudience.USER  # "user"
   
   # System domain
   TokenAudience.SYSTEM  # "system"
   ```

4. **Separate Routes**
   ```python
   # Admin domain
   /api/admin/*  # Admin-only routes
   
   # User domain
   /api/user/*  # User routes
   
   # System domain
   # No API routes (internal only)
   ```

### Token Validation

**Tokens cannot cross domains:**

```python
# Admin token cannot access user endpoints
admin_token = create_token(..., audience=TokenAudience.ADMIN)
# ❌ Fails when used on /api/user/* endpoints

# User token cannot access admin endpoints
user_token = create_token(..., audience=TokenAudience.USER)
# ❌ Fails when used on /api/admin/* endpoints
```

**Validation:**
```python
# Admin dependency validates admin audience
async def get_current_admin_user(token: str):
    payload = decode_token(token, TokenAudience.ADMIN)  # Must be ADMIN
    # ...

# User dependency validates user audience
async def get_current_user(token: str):
    payload = decode_token(token, TokenAudience.USER)  # Must be USER
    # ...
```

---

## Authentication Model

### Multi-Factor Authentication Layers

**1. Token Validation**
- JWT signature verification
- Audience validation
- Expiration checking
- Scope validation (if present)

**2. User Verification**
- Database lookup
- Active status check
- Domain verification (AdminUser vs User)

**3. Permission Checking**
- RBAC permission evaluation
- Policy engine evaluation
- Team membership verification

**4. Rate Limiting**
- Plan-based limits
- Abuse detection
- Automatic blocking

### Authentication Flow

```
1. Client Request
   └── Bearer token in Authorization header

2. Token Extraction
   └── OAuth2PasswordBearer dependency

3. Token Validation
   ├── JWT signature verification
   ├── Audience validation
   ├── Expiration check
   └── Scope extraction

4. User Lookup
   ├── Extract subject (email) from token
   ├── Query database (AdminUser or User)
   └── Verify user exists and is active

5. Authorization
   ├── RBAC permission check
   ├── Policy engine evaluation
   └── Team membership check

6. Request Processing
   └── Handler execution
```

### Password Security

**Password Hashing:**
- Bcrypt with automatic salt
- Async hashing (non-blocking)
- No plaintext storage

**Password Reset:**
- JWT-based reset tokens
- Separate secret key
- Time-limited expiration
- Single-use tokens (optional)

---

## Authorization Model

### Multi-Layer Authorization

**1. RBAC (Role-Based Access Control)**
- Permission-first design
- Role-based permissions
- Team-scoped roles
- Global roles

**2. Policy Engine (ABAC)**
- Attribute-based policies
- Dynamic evaluation
- Context-aware decisions
- Fail-closed by default

**3. Resource Ownership**
- User ownership checks
- Team membership checks
- Resource-level permissions

**4. Billing Entitlements**
- Plan-based features
- Usage limits
- Feature flags

### Authorization Flow

```
1. Permission Check
   └── Does user have required permission?

2. Policy Evaluation
   └── Do policies allow this action?

3. Resource Ownership
   └── Does user own this resource?

4. Team Membership
   └── Is user member of resource's team?

5. Billing Entitlement
   └── Does user's plan allow this feature?

6. Final Decision
   ├── All checks pass → Allow
   └── Any check fails → Deny
```

---

## Defense in Depth

### Multiple Security Layers

**1. Network Layer**
- HTTPS/TLS encryption
- CORS protection
- Rate limiting

**2. Application Layer**
- Token validation
- Permission checking
- Policy evaluation
- Input validation

**3. Data Layer**
- Database encryption
- Password hashing
- Audit logging
- Data isolation

**4. Operational Layer**
- Monitoring and alerting
- Incident response
- Security updates
- Access controls

### Security Controls

**Input Validation:**
- Pydantic models
- Type checking
- Sanitization
- SQL injection prevention

**Output Encoding:**
- JSON serialization
- XSS prevention
- Sensitive data filtering

**Error Handling:**
- Generic error messages
- No information leakage
- Audit logging
- Alert generation

---

## Security Guarantees

### What SwX-API Guarantees

✅ **Domain Isolation**
- Admin tokens cannot access user endpoints
- User tokens cannot access admin endpoints
- System tokens are internal only

✅ **Token Security**
- JWT signatures verified
- Audience validation enforced
- Expiration enforced
- Separate secrets per domain (optional)

✅ **Password Security**
- Bcrypt hashing
- No plaintext storage
- Secure reset tokens

✅ **Permission Enforcement**
- RBAC permissions checked
- Policy engine evaluated
- Fail-closed by default

✅ **Audit Logging**
- All security events logged
- Immutable audit records
- Complete accountability

### What SwX-API Does NOT Guarantee

❌ **Network Security**
- Framework assumes HTTPS/TLS
- No built-in DDoS protection
- No built-in WAF

❌ **Infrastructure Security**
- Framework assumes secure infrastructure
- No built-in secrets management
- No built-in key rotation

❌ **Application Security**
- Framework assumes secure application code
- No built-in input sanitization beyond Pydantic
- No built-in output encoding beyond JSON

---

## Threat Model

### Identified Threats

**1. Token Theft**
- **Threat:** Stolen JWT tokens
- **Mitigation:** Short expiration, refresh tokens, audience validation
- **Detection:** Audit logging, alerting

**2. Privilege Escalation**
- **Threat:** User gains admin access
- **Mitigation:** Domain separation, audience validation
- **Detection:** Audit logging, policy violations

**3. Password Attacks**
- **Threat:** Brute force, credential stuffing
- **Mitigation:** Bcrypt hashing, rate limiting, account lockout
- **Detection:** Failed login alerts, rate limit violations

**4. SQL Injection**
- **Threat:** Malicious SQL in input
- **Mitigation:** SQLModel/ORM, parameterized queries
- **Detection:** Input validation, error monitoring

**5. XSS Attacks**
- **Threat:** Malicious scripts in input
- **Mitigation:** Input validation, output encoding
- **Detection:** Content security policy, input validation

**6. CSRF Attacks**
- **Threat:** Cross-site request forgery
- **Mitigation:** SameSite cookies, CSRF tokens
- **Detection:** Origin validation, token validation

**7. Rate Limit Bypass**
- **Threat:** Bypassing rate limits
- **Mitigation:** Redis-backed limits, fail-closed
- **Detection:** Rate limit violations, abuse detection

---

## Best Practices

### ✅ DO

1. **Use HTTPS in production**
   ```python
   # ✅ Good - HTTPS enforced
   # Configure reverse proxy (nginx, Caddy) for HTTPS
   ```

2. **Rotate secrets regularly**
   ```python
   # ✅ Good - Secret rotation
   # Rotate SECRET_KEY, REFRESH_SECRET_KEY, etc. regularly
   ```

3. **Use separate secrets per domain**
   ```python
   # ✅ Good - Separate secrets
   SECRET_KEY=admin-secret
   USER_SECRET_KEY=user-secret
   SYSTEM_SECRET_KEY=system-secret
   ```

4. **Enable audit logging**
   ```python
   # ✅ Good - Audit all security events
   await audit.log_event(
       action="auth.login",
       outcome=AuditOutcome.SUCCESS,
       ...
   )
   ```

5. **Validate all input**
   ```python
   # ✅ Good - Pydantic validation
   class UserCreate(BaseModel):
       email: EmailStr  # Validated
       password: str  # Validated
   ```

### ❌ DON'T

1. **Don't store secrets in code**
   ```python
   # ❌ Bad - Secret in code
   SECRET_KEY = "hardcoded-secret"
   
   # ✅ Good - Secret in .env
   SECRET_KEY = os.getenv("SECRET_KEY")
   ```

2. **Don't log sensitive data**
   ```python
   # ❌ Bad - Password in log
   logger.info(f"User login: {email}, password: {password}")
   
   # ✅ Good - No sensitive data
   logger.info(f"User login: {email}")
   ```

3. **Don't trust user input**
   ```python
   # ❌ Bad - No validation
   user_id = request.query_params.get("user_id")
   user = await get_user(user_id)  # SQL injection risk
   
   # ✅ Good - Validated
   user_id = UUID(request.query_params.get("user_id"))
   user = await get_user(user_id)  # Type-safe
   ```

4. **Don't expose error details**
   ```python
   # ❌ Bad - Detailed error
   raise HTTPException(detail=f"SQL Error: {str(e)}")
   
   # ✅ Good - Generic error
   raise HTTPException(detail="Internal server error")
   ```

---

## Next Steps

- Read [Token Security Documentation](./TOKEN_SECURITY.md) for token security details
- Read [Secrets Management Documentation](./SECRETS_MANAGEMENT.md) for secrets handling
- Read [Security Best Practices](./SECURITY_BEST_PRACTICES.md) for production security

---

**Status:** Security model documented, ready for implementation.
