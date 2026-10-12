# Secrets Management

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Secret Types](#secret-types)
3. [Storage Locations](#storage-locations)
4. [Secret Rotation](#secret-rotation)
5. [Environment Variables](#environment-variables)
6. [Production Best Practices](#production-best-practices)
7. [Common Mistakes](#common-mistakes)
8. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API follows a **strict secrets management policy**: secrets are stored in environment variables (`.env` files), never in code or database. This ensures secrets are:

- **Secure** - Not committed to version control
- **Configurable** - Different secrets per environment
- **Rotatable** - Easy to rotate without code changes
- **Auditable** - Access controlled via environment

### Key Principles

1. **Never in Code** - Secrets never hardcoded
2. **Never in Database** - Secrets never stored in database
3. **Environment Variables** - All secrets in `.env` files
4. **Separate Per Environment** - Different secrets per environment
5. **Rotate Regularly** - Secrets rotated periodically

---

## Secret Types

### 1. JWT Secret Keys

**Purpose:** Signing and verifying JWT tokens

**Secrets:**
- `SECRET_KEY` - Primary JWT signing key
- `REFRESH_SECRET_KEY` - Refresh token signing key (optional)
- `PASSWORD_RESET_SECRET_KEY` - Password reset token signing key

**Characteristics:**
- Must be strong (32+ characters, random)
- Should be different per environment
- Should be rotated periodically
- Never shared across environments

**Usage:**
```python
from swx_core.config.settings import settings

# Access secret key
secret_key = settings.SECRET_KEY
```

### 2. Database Credentials

**Purpose:** Database connection authentication

**Secrets:**
- `DB_PASSWORD` - Database password
- `DB_USER` - Database username (if sensitive)

**Characteristics:**
- Database-specific
- Should be strong passwords
- Rotated when compromised
- Different per environment

**Usage:**
```python
# Database URL constructed from secrets
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

### 3. Redis Credentials

**Purpose:** Redis connection authentication

**Secrets:**
- `REDIS_PASSWORD` - Redis password (if enabled)

**Characteristics:**
- Optional (if Redis requires auth)
- Should be strong passwords
- Rotated when compromised

**Usage:**
```python
# Redis URL constructed from secrets
redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
```

### 4. Email Service Credentials

**Purpose:** SMTP authentication

**Secrets:**
- `SMTP_PASSWORD` - SMTP password
- `SMTP_USER` - SMTP username (if sensitive)

**Characteristics:**
- Email service-specific
- Should be strong passwords
- Rotated when compromised

**Usage:**
```python
# SMTP configuration from secrets
smtp_config = {
    "host": SMTP_HOST,
    "port": SMTP_PORT,
    "user": SMTP_USER,
    "password": SMTP_PASSWORD
}
```

### 5. OAuth Client Secrets

**Purpose:** OAuth provider authentication

**Secrets:**
- `GOOGLE_CLIENT_SECRET` - Google OAuth secret
- `FACEBOOK_CLIENT_SECRET` - Facebook OAuth secret

**Characteristics:**
- Provider-specific
- Should be strong secrets
- Rotated when compromised
- Different per environment

**Usage:**
```python
# OAuth configuration from secrets
google_config = {
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET
}
```

### 6. Third-Party API Keys

**Purpose:** External service authentication

**Secrets:**
- `SENTRY_DSN` - Sentry error tracking (contains token)
- `STRIPE_SECRET_KEY` - Stripe API key
- Any other API keys

**Characteristics:**
- Service-specific
- Should be strong keys
- Rotated when compromised
- Different per environment

---

## Storage Locations

### ✅ Correct: Environment Variables

**All secrets stored in `.env` files:**

```bash
# .env
SECRET_KEY=your-secret-key-here
REFRESH_SECRET_KEY=your-refresh-secret-key
PASSWORD_RESET_SECRET_KEY=your-reset-secret-key
DB_PASSWORD=your-database-password
REDIS_PASSWORD=your-redis-password
SMTP_PASSWORD=your-smtp-password
GOOGLE_CLIENT_SECRET=your-google-secret
FACEBOOK_CLIENT_SECRET=your-facebook-secret
SENTRY_DSN=your-sentry-dsn
```

**Access in Code:**
```python
from swx_core.config.settings import settings

# Secrets accessed via settings
secret_key = settings.SECRET_KEY
db_password = settings.DB_PASSWORD
```

### ❌ Wrong: Hardcoded Secrets

**Never hardcode secrets:**

```python
# ❌ BAD - Secret in code
SECRET_KEY = "hardcoded-secret-key"

# ✅ GOOD - Secret in .env
SECRET_KEY = os.getenv("SECRET_KEY")
```

### ❌ Wrong: Database Storage

**Never store secrets in database:**

```python
# ❌ BAD - Secret in database
SystemConfig(
    key="stripe.secret_key",
    value="sk_live_..."  # DON'T DO THIS
)

# ✅ GOOD - Secret in .env
STRIPE_SECRET_KEY=sk_live_...  # In .env
```

### ❌ Wrong: Version Control

**Never commit secrets to git:**

```bash
# ❌ BAD - Secret in git
# .env committed to repository

# ✅ GOOD - .env in .gitignore
# .env
# *.env
# .env.*
```

---

## Secret Rotation

### Rotation Strategy

**1. Regular Rotation**
- Rotate secrets periodically (e.g., every 90 days)
- Rotate immediately if compromised
- Rotate when employees leave

**2. Gradual Rotation**
- Support multiple secrets during rotation
- Gradually migrate to new secret
- Remove old secret after migration

**3. Zero-Downtime Rotation**
- Update secret in environment
- Restart application
- Old tokens continue to work until expiration
- New tokens use new secret

### Rotation Process

**Step 1: Generate New Secret**
```bash
# Generate strong random secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Step 2: Update Environment**
```bash
# Update .env file
SECRET_KEY=new-secret-key-here
```

**Step 3: Restart Application**
```bash
# Restart to load new secret
docker compose restart swx-api
```

**Step 4: Verify**
```bash
# Test authentication
curl -X POST http://localhost:8001/api/auth \
  -d "email=user@example.com&password=password"
```

**Step 5: Monitor**
- Monitor for authentication failures
- Check audit logs for issues
- Verify new tokens work

### Token Expiration During Rotation

**Access Tokens:**
- Old tokens continue to work until expiration
- New tokens use new secret
- Gradual migration as tokens expire

**Refresh Tokens:**
- Old refresh tokens may fail
- Users need to re-authenticate
- Or support dual-secret validation during rotation

---

## Environment Variables

### .env File Structure

**Development (.env):**
```bash
# JWT Secrets
SECRET_KEY=dev-secret-key-32-chars-minimum
REFRESH_SECRET_KEY=dev-refresh-secret-key
PASSWORD_RESET_SECRET_KEY=dev-reset-secret-key

# Database
DB_PASSWORD=dev-db-password

# Redis
REDIS_PASSWORD=dev-redis-password

# Email
SMTP_PASSWORD=dev-smtp-password

# OAuth
GOOGLE_CLIENT_SECRET=dev-google-secret
FACEBOOK_CLIENT_SECRET=dev-facebook-secret

# Third-party
SENTRY_DSN=dev-sentry-dsn
```

**Production (.env.production):**
```bash
# JWT Secrets (different from dev)
SECRET_KEY=prod-secret-key-32-chars-minimum
REFRESH_SECRET_KEY=prod-refresh-secret-key
PASSWORD_RESET_SECRET_KEY=prod-reset-secret-key

# Database (different from dev)
DB_PASSWORD=prod-db-password

# ... other secrets
```

### Loading Environment Variables

**Via pydantic-settings:**
```python
# swx_core/config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    DB_PASSWORD: str
    # ... other secrets
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Via python-dotenv:**
```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file
```

---

## Production Best Practices

### ✅ DO

1. **Use strong secrets**
   ```bash
   # ✅ Good - Strong secret (32+ characters, random)
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

2. **Use different secrets per environment**
   ```bash
   # ✅ Good - Different secrets
   # Dev: SECRET_KEY=dev-secret
   # Prod: SECRET_KEY=prod-secret
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

5. **Restrict .env file permissions**
   ```bash
   # ✅ Good - Restrict file permissions
   chmod 600 .env  # Owner read/write only
   ```

6. **Use .env.example for documentation**
   ```bash
   # ✅ Good - Document required secrets
   # .env.example (committed to git)
   SECRET_KEY=your-secret-key-here
   DB_PASSWORD=your-database-password
   ```

### ❌ DON'T

1. **Don't commit .env to git**
   ```bash
   # ❌ Bad - .env in git
   git add .env
   
   # ✅ Good - .env in .gitignore
   echo ".env" >> .gitignore
   ```

2. **Don't share secrets across environments**
   ```bash
   # ❌ Bad - Same secret everywhere
   SECRET_KEY=shared-secret  # Dev, staging, prod
   
   # ✅ Good - Different secrets
   SECRET_KEY=dev-secret     # Dev
   SECRET_KEY=staging-secret # Staging
   SECRET_KEY=prod-secret    # Prod
   ```

3. **Don't use weak secrets**
   ```bash
   # ❌ Bad - Weak secret
   SECRET_KEY=password123
   
   # ✅ Good - Strong secret
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

4. **Don't log secrets**
   ```python
   # ❌ Bad - Secret in logs
   logger.info(f"SECRET_KEY: {settings.SECRET_KEY}")
   
   # ✅ Good - No secrets in logs
   logger.info("Application started")
   ```

5. **Don't expose secrets in error messages**
   ```python
   # ❌ Bad - Secret in error
   raise Exception(f"Database error: {DB_PASSWORD}")
   
   # ✅ Good - Generic error
   raise Exception("Database connection failed")
   ```

---

## Common Mistakes

### Mistake 1: Hardcoded Secrets

**Problem:**
```python
# ❌ Bad - Secret in code
SECRET_KEY = "my-secret-key"
```

**Fix:**
```python
# ✅ Good - Secret in .env
SECRET_KEY = os.getenv("SECRET_KEY")
```

### Mistake 2: Committing .env to Git

**Problem:**
```bash
# ❌ Bad - .env committed
git add .env
git commit -m "Add .env"
```

**Fix:**
```bash
# ✅ Good - .env in .gitignore
echo ".env" >> .gitignore
```

### Mistake 3: Sharing Secrets Across Environments

**Problem:**
```bash
# ❌ Bad - Same secret everywhere
SECRET_KEY=shared-secret  # Dev, staging, prod
```

**Fix:**
```bash
# ✅ Good - Different secrets per environment
# Dev: SECRET_KEY=dev-secret
# Prod: SECRET_KEY=prod-secret
```

### Mistake 4: Weak Secrets

**Problem:**
```bash
# ❌ Bad - Weak secret
SECRET_KEY=password
```

**Fix:**
```bash
# ✅ Good - Strong secret
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

---

## Troubleshooting

### Common Issues

**1. "Secret key not found" errors**
- Check `.env` file exists
- Verify secret key is set in `.env`
- Check environment variable name matches
- Verify `.env` file is loaded

**2. "Invalid token signature" errors**
- Check secret key matches between environments
- Verify secret key hasn't been rotated
- Check for secret key typos

**3. "Database connection failed" errors**
- Check database password in `.env`
- Verify database credentials are correct
- Check database host/port/name

**4. "SMTP authentication failed" errors**
- Check SMTP password in `.env`
- Verify SMTP credentials are correct
- Check SMTP host/port

### Debugging

**Check environment variables:**
```python
import os

# Check if secret is loaded
print(os.getenv("SECRET_KEY"))  # Should print secret (in dev only)
```

**Verify .env file loading:**
```python
from dotenv import load_dotenv
load_dotenv()  # Explicitly load .env

# Check if loaded
import os
print(os.getenv("SECRET_KEY"))
```

**Generate strong secret:**
```python
import secrets

# Generate strong secret
secret = secrets.token_urlsafe(32)
print(secret)
```

---

## Next Steps

- Read [Security Best Practices](./SECURITY_BEST_PRACTICES.md) for production security
- Read [Token Security Documentation](./TOKEN_SECURITY.md) for token handling
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production deployment

---

**Status:** Secrets management documented, ready for implementation.
