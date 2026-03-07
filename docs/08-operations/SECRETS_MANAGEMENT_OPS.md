# Secrets Management Operations

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Secret Storage](#secret-storage)
3. [Secret Rotation](#secret-rotation)
4. [Secret Access](#secret-access)
5. [Production Best Practices](#production-best-practices)
6. [Secrets Management Services](#secrets-management-services)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers **operational aspects of secrets management** in SwX-API, including storage, rotation, access control, and production best practices.

### Key Principles

1. **Never in Code** - Secrets never hardcoded
2. **Never in Database** - Secrets never stored in database
3. **Environment Variables** - All secrets in `.env` files
4. **Separate Per Environment** - Different secrets per environment
5. **Rotate Regularly** - Secrets rotated periodically

---

## Secret Storage

### Development Storage

**Local `.env` File:**
```bash
# .env (not committed to git)
SECRET_KEY=dev-secret-key-32-chars-minimum
DB_PASSWORD=dev-db-password
SMTP_PASSWORD=dev-smtp-password
```

**Security:**
- File permissions: `chmod 600 .env`
- Not committed to git
- Different secrets per developer (optional)

### Production Storage

**Option 1: Environment Variables**
```bash
# Set in production environment
export SECRET_KEY=prod-secret-key
export DB_PASSWORD=prod-db-password
```

**Option 2: Secrets Management Service**
```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id swx-api/secrets

# HashiCorp Vault
vault kv get secret/swx-api/secrets
```

**Option 3: Docker Secrets**
```yaml
# docker-compose.yml
secrets:
  secret_key:
    external: true

services:
  swx-api:
    secrets:
      - secret_key
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

# Or update in secrets management service
aws secretsmanager update-secret --secret-id swx-api/secrets --secret-string '{"SECRET_KEY":"new-secret-key"}'
```

**Step 3: Restart Application**
```bash
# Restart to load new secret
docker compose restart swx-api

# Or rolling restart
docker compose up -d --no-deps swx-api
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

## Secret Access

### Access Control

**File Permissions:**
```bash
# Restrict .env file permissions
chmod 600 .env  # Owner read/write only

# Verify permissions
ls -l .env
```

**Environment Variables:**
```bash
# Set in user environment (not system-wide)
export SECRET_KEY=secret-key

# Or in user's .bashrc (not recommended for production)
echo 'export SECRET_KEY=secret-key' >> ~/.bashrc
```

**Secrets Management Services:**
- Use IAM roles for access control
- Use Vault policies for access control
- Audit secret access

### Access Logging

**Audit Secret Access:**
```python
# Log secret access (if implemented)
await audit.log_event(
    action="secret.accessed",
    resource_type="secret",
    resource_id="SECRET_KEY",
    ...
)
```

**Monitor Secret Usage:**
- Monitor authentication failures (may indicate secret issues)
- Monitor token validation errors
- Alert on unusual patterns

---

## Production Best Practices

### ✅ DO

1. **Use secrets management service**
   ```bash
   # ✅ Good - AWS Secrets Manager
   aws secretsmanager get-secret-value --secret-id swx-api/secrets
   
   # ✅ Good - HashiCorp Vault
   vault kv get secret/swx-api/secrets
   ```

2. **Rotate secrets regularly**
   ```bash
   # ✅ Good - Rotate every 90 days
   # Or immediately if compromised
   ```

3. **Use different secrets per environment**
   ```bash
   # ✅ Good - Different secrets
   # Dev: SECRET_KEY=dev-secret
   # Prod: SECRET_KEY=prod-secret
   ```

4. **Restrict file permissions**
   ```bash
   # ✅ Good - Restrict permissions
   chmod 600 .env
   ```

5. **Use strong secrets**
   ```bash
   # ✅ Good - Strong secret (32+ characters, random)
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

6. **Backup secrets securely**
   ```bash
   # ✅ Good - Encrypted backup
   # Store in secure location
   # Encrypt before storing
   ```

### ❌ DON'T

1. **Don't commit secrets to git**
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
   SECRET_KEY=prod-secret    # Prod
   ```

3. **Don't use weak secrets**
   ```bash
   # ❌ Bad - Weak secret
   SECRET_KEY=password
   
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

## Secrets Management Services

### AWS Secrets Manager

**Setup:**
```bash
# Create secret
aws secretsmanager create-secret \
  --name swx-api/secrets \
  --secret-string '{"SECRET_KEY":"secret-key","DB_PASSWORD":"db-password"}'

# Retrieve secret
aws secretsmanager get-secret-value --secret-id swx-api/secrets

# Update secret
aws secretsmanager update-secret \
  --secret-id swx-api/secrets \
  --secret-string '{"SECRET_KEY":"new-secret-key"}'
```

**Usage:**
```python
# Load secrets from AWS Secrets Manager
import boto3
import json

secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId='swx-api/secrets')
secrets = json.loads(response['SecretString'])

SECRET_KEY = secrets['SECRET_KEY']
DB_PASSWORD = secrets['DB_PASSWORD']
```

### HashiCorp Vault

**Setup:**
```bash
# Store secret
vault kv put secret/swx-api/secrets \
  SECRET_KEY=secret-key \
  DB_PASSWORD=db-password

# Retrieve secret
vault kv get secret/swx-api/secrets
```

**Usage:**
```python
# Load secrets from Vault
import hvac

client = hvac.Client(url='https://vault.example.com')
client.token = 'your-vault-token'

secrets = client.secrets.kv.v2.read_secret_version(path='swx-api/secrets')
SECRET_KEY = secrets['data']['data']['SECRET_KEY']
DB_PASSWORD = secrets['data']['data']['DB_PASSWORD']
```

### Docker Secrets

**Setup:**
```bash
# Create secret
echo "secret-key" | docker secret create secret_key -

# Use in docker-compose.yml
secrets:
  secret_key:
    external: true

services:
  swx-api:
    secrets:
      - secret_key
```

**Usage:**
```python
# Read secret from file
with open('/run/secrets/secret_key', 'r') as f:
    SECRET_KEY = f.read().strip()
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

**Check Environment Variables:**
```python
import os

# Check if secret is loaded
print(os.getenv("SECRET_KEY"))  # Should print secret (in dev only)
```

**Verify .env File Loading:**
```python
from dotenv import load_dotenv
load_dotenv()  # Explicitly load .env

# Check if loaded
import os
print(os.getenv("SECRET_KEY"))
```

**Generate Strong Secret:**
```python
import secrets

# Generate strong secret
secret = secrets.token_urlsafe(32)
print(secret)
```

---

## Next Steps

- Read [Secrets Management Documentation](../05-security/SECRETS_MANAGEMENT.md) for security details
- Read [Operations Guide](./OPERATIONS.md) for day-to-day operations
- Read [Production Checklist](./PRODUCTION_CHECKLIST.md) for production readiness

---

**Status:** Secrets management operations documented, ready for implementation.
