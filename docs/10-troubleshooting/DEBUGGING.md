# Debugging Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Debug Logging](#debug-logging)
3. [Database Debugging](#database-debugging)
4. [Redis Debugging](#redis-debugging)
5. [Token Debugging](#token-debugging)
6. [Request Debugging](#request-debugging)
7. [Performance Debugging](#performance-debugging)

---

## Overview

This guide covers **debugging techniques and tools** for SwX-API. Use these techniques to diagnose and resolve issues effectively.

### Debugging Principles

1. **Start with Logs** - Check application logs first
2. **Isolate the Issue** - Narrow down to specific component
3. **Reproduce Consistently** - Ensure issue is reproducible
4. **Use Debug Tools** - Leverage debugging tools
5. **Document Findings** - Keep track of debugging steps

---

## Debug Logging

### Enable Debug Logging

**Environment Variable:**
```bash
export LOG_LEVEL=DEBUG
```

**In Code:**
```python
import logging
logging.getLogger("swx_core").setLevel(logging.DEBUG)
```

### View Debug Logs

**Docker Logs:**
```bash
# Follow logs
docker compose logs -f swx-api

# Filter debug logs
docker compose logs swx-api | grep DEBUG

# Last 100 lines
docker compose logs --tail=100 swx-api
```

### Logging Best Practices

**DO:**
- Log important events
- Include context (user_id, request_id)
- Use appropriate log levels

**DON'T:**
- Log sensitive data
- Log too verbosely
- Log in production (use INFO or higher)

---

## Database Debugging

### Connect to Database

**PostgreSQL:**
```bash
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME}
```

### Common Queries

**Check Tables:**
```sql
-- List all tables
\dt

-- Describe table
\d "user"

-- Count records
SELECT COUNT(*) FROM "user";
```

**Check Data:**
```sql
-- Get user
SELECT * FROM "user" WHERE email = 'user@example.com';

-- Get audit logs
SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10;

-- Check foreign keys
SELECT * FROM user_role ur
LEFT JOIN "user" u ON ur.user_id = u.id
WHERE u.id IS NULL;
```

**Check Performance:**
```sql
-- Slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Active connections
SELECT * FROM pg_stat_activity 
WHERE state = 'active';

-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Redis Debugging

### Connect to Redis

**Redis CLI:**
```bash
docker compose exec redis redis-cli
```

### Common Commands

**Check Keys:**
```bash
# List all keys
KEYS *

# List rate limit keys
KEYS rate_limit:*

# Count keys
DBSIZE
```

**Check Memory:**
```bash
# Memory info
INFO memory

# Memory usage
MEMORY USAGE key_name
```

**Monitor Commands:**
```bash
# Monitor all commands
MONITOR

# Check specific key
GET key_name

# Check TTL
TTL key_name
```

**Clear Data:**
```bash
# Clear all keys (use with caution)
FLUSHALL

# Clear specific key
DEL key_name
```

---

## Token Debugging

### Decode Token

**Python:**
```python
import jwt

# Decode without verification (for debugging)
payload = jwt.decode(token, options={"verify_signature": False})
print(payload)
```

**Check Token Expiration:**
```python
import jwt
from datetime import datetime

payload = jwt.decode(token, options={"verify_signature": False})
exp = payload.get("exp")
exp_time = datetime.fromtimestamp(exp)
print(f"Token expires: {exp_time}")
```

**Check Token Audience:**
```python
payload = jwt.decode(token, options={"verify_signature": False})
aud = payload.get("aud")
print(f"Token audience: {aud}")
```

### Verify Token

**Check Signature:**
```python
import jwt
from swx_core.config.settings import settings

try:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"]
    )
    print("Token signature valid")
except jwt.InvalidSignatureError:
    print("Token signature invalid")
```

---

## Request Debugging

### Enable Request Logging

**Middleware:**
```python
# Request logging is enabled by default
# Check logs for request details
```

### Debug Request Flow

**Add Debug Points:**
```python
# In route handler
@router.get("/endpoint")
async def endpoint(request: Request):
    logger.debug(f"Request: {request.method} {request.url.path}")
    logger.debug(f"Headers: {dict(request.headers)}")
    logger.debug(f"Query params: {dict(request.query_params)}")
    ...
```

### Trace Request ID

**Request ID:**
```python
# Request ID is set by middleware
request_id = getattr(request.state, "request_id", None)
logger.debug(f"Request ID: {request_id}")
```

---

## Performance Debugging

### Profile Requests

**Timing:**
```python
import time

start = time.time()
result = await operation()
duration = time.time() - start
logger.info(f"Operation took {duration}s")
```

### Database Query Profiling

**Enable Query Logging:**
```python
# In database configuration
engine = create_async_engine(
    DATABASE_URL,
    echo=True  # Log all SQL queries
)
```

**Check Query Performance:**
```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Memory Profiling

**Check Memory Usage:**
```bash
# Container memory
docker stats

# Process memory
docker compose exec swx-api ps aux

# Python memory
docker compose exec swx-api python -c "
import sys
print(sys.getsizeof(object))
"
```

---

## Next Steps

- Read [Troubleshooting Guide](./TROUBLESHOOTING.md) for common issues
- Read [FAQ](./FAQ.md) for common questions
- Read [Operations Guide](../08-operations/OPERATIONS.md) for operations

---

**Status:** Debugging guide documented, ready for implementation.
