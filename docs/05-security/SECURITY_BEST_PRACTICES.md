# Security Best Practices

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Development Security](#development-security)
3. [Production Security](#production-security)
4. [Authentication Security](#authentication-security)
5. [Authorization Security](#authorization-security)
6. [Data Security](#data-security)
7. [Network Security](#network-security)
8. [Monitoring & Incident Response](#monitoring--incident-response)
9. [Compliance](#compliance)
10. [Security Checklist](#security-checklist)

---

## Overview

This document provides **comprehensive security best practices** for developing, deploying, and operating SwX-API applications. Follow these practices to ensure your application is secure.

### Security Principles

1. **Defense in Depth** - Multiple security layers
2. **Least Privilege** - Minimum necessary permissions
3. **Fail-Closed** - Security failures deny access
4. **Audit Everything** - All security events logged
5. **Secure by Default** - Secure configuration out of the box

---

## Development Security

### ✅ DO

1. **Never commit secrets**
   ```bash
   # ✅ Good - .env in .gitignore
   echo ".env" >> .gitignore
   echo "*.env" >> .gitignore
   ```

2. **Use strong secrets in development**
   ```bash
   # ✅ Good - Strong dev secrets
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

3. **Validate all input**
   ```python
   # ✅ Good - Pydantic validation
   class UserCreate(BaseModel):
       email: EmailStr  # Validated
       password: str = Field(min_length=8)  # Validated
   ```

4. **Use parameterized queries**
   ```python
   # ✅ Good - SQLModel/ORM (parameterized)
   stmt = select(User).where(User.email == email)
   result = await session.execute(stmt)
   ```

5. **Sanitize output**
   ```python
   # ✅ Good - JSON serialization (safe)
   return JSONResponse(content=user.dict())
   ```

6. **Handle errors securely**
   ```python
   # ✅ Good - Generic error messages
   try:
       result = await operation()
   except Exception:
       raise HTTPException(500, "Internal server error")
   ```

### ❌ DON'T

1. **Don't log sensitive data**
   ```python
   # ❌ Bad - Password in logs
   logger.info(f"User login: {email}, password: {password}")
   
   # ✅ Good - No sensitive data
   logger.info(f"User login: {email}")
   ```

2. **Don't expose error details**
   ```python
   # ❌ Bad - Detailed error
   raise HTTPException(500, detail=f"SQL Error: {str(e)}")
   
   # ✅ Good - Generic error
   raise HTTPException(500, detail="Internal server error")
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

4. **Don't use weak secrets**
   ```bash
   # ❌ Bad - Weak secret
   SECRET_KEY=password
   
   # ✅ Good - Strong secret
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

---

## Production Security

### ✅ DO

1. **Use HTTPS/TLS**
   ```nginx
   # ✅ Good - HTTPS enforced
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
   }
   ```

2. **Use strong secrets**
   ```bash
   # ✅ Good - Strong production secrets
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
   ```

3. **Rotate secrets regularly**
   ```bash
   # ✅ Good - Rotate every 90 days
   # Or immediately if compromised
   ```

4. **Use secrets management service**
   ```bash
   # ✅ Good - AWS Secrets Manager, HashiCorp Vault, etc.
   # For production environments
   ```

5. **Enable security headers**
   ```python
   # ✅ Good - Security headers
   @app.middleware("http")
   async def security_headers(request, call_next):
       response = await call_next(request)
       response.headers["X-Content-Type-Options"] = "nosniff"
       response.headers["X-Frame-Options"] = "DENY"
       response.headers["X-XSS-Protection"] = "1; mode=block"
       return response
   ```

6. **Enable CORS properly**
   ```python
   # ✅ Good - Restrictive CORS
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://example.com"],  # Specific origins
       allow_credentials=True,
       allow_methods=["GET", "POST"],
       allow_headers=["Authorization"],
   )
   ```

7. **Enable rate limiting**
   ```python
   # ✅ Good - Rate limiting enabled
   app.add_middleware(RateLimitMiddleware)
   ```

8. **Enable audit logging**
   ```python
   # ✅ Good - All security events logged
   await audit.log_event(
       action="auth.login",
       outcome=AuditOutcome.SUCCESS,
       ...
   )
   ```

### ❌ DON'T

1. **Don't use development secrets in production**
   ```bash
   # ❌ Bad - Dev secret in prod
   SECRET_KEY=dev-secret-key  # In production
   
   # ✅ Good - Different secrets
   SECRET_KEY=prod-secret-key  # In production
   ```

2. **Don't disable security features**
   ```python
   # ❌ Bad - Security disabled
   CORS_ORIGINS = ["*"]  # Too permissive
   
   # ✅ Good - Security enabled
   CORS_ORIGINS = ["https://example.com"]  # Specific
   ```

3. **Don't expose debug information**
   ```python
   # ❌ Bad - Debug mode in production
   DEBUG = True  # In production
   
   # ✅ Good - Debug disabled
   DEBUG = False  # In production
   ```

---

## Authentication Security

### ✅ DO

1. **Use strong password requirements**
   ```python
   # ✅ Good - Strong password requirements
   password: str = Field(
       min_length=8,
       max_length=128,
       regex="^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
   )
   ```

2. **Hash passwords with bcrypt**
   ```python
   # ✅ Good - Bcrypt hashing
   hashed_password = await get_password_hash(password)
   ```

3. **Use short access token expiration**
   ```python
   # ✅ Good - Short expiration
   access_token_expires = timedelta(days=7)
   ```

4. **Use long refresh token expiration**
   ```python
   # ✅ Good - Long expiration
   refresh_token_expires = timedelta(days=30)
   ```

5. **Validate audience on every request**
   ```python
   # ✅ Good - Audience validation
   payload = decode_token(token, TokenAudience.USER)
   ```

6. **Revoke tokens on logout**
   ```python
   # ✅ Good - Revoke on logout
   await revoke_refresh_token(session, refresh_token)
   ```

7. **Rate limit authentication endpoints**
   ```python
   # ✅ Good - Rate limit login
   # Prevents brute force attacks
   ```

### ❌ DON'T

1. **Don't store plaintext passwords**
   ```python
   # ❌ Bad - Plaintext password
   user.password = password  # DON'T DO THIS
   
   # ✅ Good - Hashed password
   user.password = await get_password_hash(password)
   ```

2. **Don't use weak password requirements**
   ```python
   # ❌ Bad - Weak requirements
   password: str  # No requirements
   
   # ✅ Good - Strong requirements
   password: str = Field(min_length=8, ...)
   ```

3. **Don't use long access token expiration**
   ```python
   # ❌ Bad - Long expiration
   access_token_expires = timedelta(days=365)  # Too long
   
   # ✅ Good - Short expiration
   access_token_expires = timedelta(days=7)
   ```

---

## Authorization Security

### ✅ DO

1. **Use permission-first RBAC**
   ```python
   # ✅ Good - Permission check
   if not await has_permission(session, user, "user:delete"):
       raise HTTPException(403, "Permission denied")
   ```

2. **Use policy engine for complex rules**
   ```python
   # ✅ Good - Policy evaluation
   if not await policy_engine.evaluate(user, action, resource):
       raise HTTPException(403, "Policy denied")
   ```

3. **Check resource ownership**
   ```python
   # ✅ Good - Ownership check
   if resource.user_id != user.id:
       raise HTTPException(403, "Not resource owner")
   ```

4. **Check team membership**
   ```python
   # ✅ Good - Team membership check
   if not await is_team_member(session, user, team):
       raise HTTPException(403, "Not team member")
   ```

5. **Fail-closed by default**
   ```python
   # ✅ Good - Fail-closed
   if not has_permission:
       raise HTTPException(403, "Permission denied")
   ```

### ❌ DON'T

1. **Don't trust client-side permissions**
   ```python
   # ❌ Bad - Client-side check only
   # if (user.hasPermission("delete")) { ... }  // JavaScript
   
   # ✅ Good - Server-side check
   if not await has_permission(session, user, "delete"):
       raise HTTPException(403)
   ```

2. **Don't skip permission checks**
   ```python
   # ❌ Bad - No permission check
   await delete_user(session, user_id)
   
   # ✅ Good - Permission checked
   if not await has_permission(session, user, "user:delete"):
       raise HTTPException(403)
   await delete_user(session, user_id)
   ```

---

## Data Security

### ✅ DO

1. **Encrypt sensitive data at rest**
   ```python
   # ✅ Good - Encrypted database
   # Use database encryption (PostgreSQL encryption)
   ```

2. **Use HTTPS for data in transit**
   ```nginx
   # ✅ Good - HTTPS enforced
   server {
       listen 443 ssl;
   }
   ```

3. **Filter sensitive data from logs**
   ```python
   # ✅ Good - Filtered context
   safe_context = filter_sensitive_data(context)
   await audit.log_event(..., context=safe_context)
   ```

4. **Use parameterized queries**
   ```python
   # ✅ Good - SQLModel/ORM (parameterized)
   stmt = select(User).where(User.email == email)
   ```

5. **Validate and sanitize input**
   ```python
   # ✅ Good - Pydantic validation
   class UserCreate(BaseModel):
       email: EmailStr  # Validated
   ```

### ❌ DON'T

1. **Don't store sensitive data in plaintext**
   ```python
   # ❌ Bad - Plaintext storage
   user.credit_card = "1234-5678-9012-3456"
   
   # ✅ Good - Encrypted storage
   user.credit_card_encrypted = encrypt(credit_card)
   ```

2. **Don't log sensitive data**
   ```python
   # ❌ Bad - Sensitive data in logs
   logger.info(f"User: {email}, password: {password}")
   
   # ✅ Good - No sensitive data
   logger.info(f"User: {email}")
   ```

---

## Network Security

### ✅ DO

1. **Use HTTPS/TLS**
   ```nginx
   # ✅ Good - HTTPS enforced
   server {
       listen 443 ssl;
   }
   ```

2. **Use restrictive CORS**
   ```python
   # ✅ Good - Restrictive CORS
   allow_origins=["https://example.com"]
   ```

3. **Use security headers**
   ```python
   # ✅ Good - Security headers
   response.headers["X-Content-Type-Options"] = "nosniff"
   response.headers["X-Frame-Options"] = "DENY"
   ```

4. **Enable rate limiting**
   ```python
   # ✅ Good - Rate limiting
   app.add_middleware(RateLimitMiddleware)
   ```

5. **Use firewall rules**
   ```bash
   # ✅ Good - Firewall rules
   # Only allow necessary ports
   ```

### ❌ DON'T

1. **Don't use HTTP in production**
   ```nginx
   # ❌ Bad - HTTP only
   server {
       listen 80;
   }
   
   # ✅ Good - HTTPS
   server {
       listen 443 ssl;
   }
   ```

2. **Don't use permissive CORS**
   ```python
   # ❌ Bad - Permissive CORS
   allow_origins=["*"]
   
   # ✅ Good - Restrictive CORS
   allow_origins=["https://example.com"]
   ```

---

## Monitoring & Incident Response

### ✅ DO

1. **Enable audit logging**
   ```python
   # ✅ Good - All security events logged
   await audit.log_event(
       action="auth.login",
       outcome=AuditOutcome.SUCCESS,
       ...
   )
   ```

2. **Enable alerting**
   ```python
   # ✅ Good - Security alerts
   await alert_engine.emit(
       severity=AlertSeverity.WARNING,
       source=AlertSource.AUTH,
       event_type="LOGIN_FAILURE_BURST",
       ...
   )
   ```

3. **Monitor authentication failures**
   ```python
   # ✅ Good - Monitor failures
   # Alert on multiple failures
   ```

4. **Monitor rate limit violations**
   ```python
   # ✅ Good - Monitor violations
   # Alert on abuse patterns
   ```

5. **Have incident response plan**
   ```markdown
   # ✅ Good - Incident response plan
   1. Identify incident
   2. Contain incident
   3. Eradicate threat
   4. Recover systems
   5. Post-incident review
   ```

### ❌ DON'T

1. **Don't ignore security alerts**
   ```python
   # ❌ Bad - Alerts ignored
   # No alerting configured
   
   # ✅ Good - Alerts configured
   await alert_engine.emit(...)
   ```

2. **Don't skip audit logging**
   ```python
   # ❌ Bad - No audit logging
   # await audit.log_event(...)  # Commented out
   
   # ✅ Good - Audit logging enabled
   await audit.log_event(...)
   ```

---

## Compliance

### ✅ DO

1. **Maintain audit logs**
   ```python
   # ✅ Good - Immutable audit logs
   # All security events logged
   ```

2. **Implement data retention policies**
   ```python
   # ✅ Good - Retention policy
   audit.retention_days = 365  # Configurable
   ```

3. **Implement access controls**
   ```python
   # ✅ Good - Access controls
   # Admin-only audit log access
   ```

4. **Document security practices**
   ```markdown
   # ✅ Good - Security documentation
   # This document and others
   ```

### ❌ DON'T

1. **Don't skip compliance requirements**
   ```python
   # ❌ Bad - No audit logging
   # Compliance requires audit logs
   
   # ✅ Good - Audit logging enabled
   await audit.log_event(...)
   ```

---

## Security Checklist

### Development

- [ ] Secrets not committed to git
- [ ] Strong secrets in development
- [ ] Input validation on all endpoints
- [ ] Output sanitization
- [ ] Error handling doesn't leak information
- [ ] No sensitive data in logs

### Production

- [ ] HTTPS/TLS enabled
- [ ] Strong production secrets
- [ ] Secrets rotated regularly
- [ ] Security headers enabled
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] Alerting configured
- [ ] Monitoring in place

### Authentication

- [ ] Strong password requirements
- [ ] Passwords hashed with bcrypt
- [ ] Short access token expiration
- [ ] Long refresh token expiration
- [ ] Audience validation enabled
- [ ] Token revocation on logout
- [ ] Rate limiting on auth endpoints

### Authorization

- [ ] Permission checks on all endpoints
- [ ] Policy engine for complex rules
- [ ] Resource ownership checks
- [ ] Team membership checks
- [ ] Fail-closed by default

### Data Security

- [ ] Sensitive data encrypted at rest
- [ ] HTTPS for data in transit
- [ ] Sensitive data filtered from logs
- [ ] Parameterized queries used
- [ ] Input validation and sanitization

### Network Security

- [ ] HTTPS/TLS enabled
- [ ] Restrictive CORS
- [ ] Security headers enabled
- [ ] Rate limiting enabled
- [ ] Firewall rules configured

### Monitoring

- [ ] Audit logging enabled
- [ ] Alerting configured
- [ ] Authentication failures monitored
- [ ] Rate limit violations monitored
- [ ] Incident response plan in place

---

## Next Steps

- Read [Security Model Documentation](./SECURITY_MODEL.md) for security architecture
- Read [Token Security Documentation](./TOKEN_SECURITY.md) for token handling
- Read [Secrets Management Documentation](./SECRETS_MANAGEMENT.md) for secrets handling
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production deployment

---

**Status:** Security best practices documented, ready for implementation.
