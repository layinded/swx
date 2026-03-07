# Rate Limiting & Abuse Protection

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Rate Limit Model](#rate-limit-model)
3. [Limit Types](#limit-types)
4. [Plan-Based Limits](#plan-based-limits)
5. [Rate Limit Algorithm](#rate-limit-algorithm)
6. [Skip Paths](#skip-paths)
7. [Usage Examples](#usage-examples)
8. [Abuse Detection](#abuse-detection)
9. [Operational Tuning](#operational-tuning)
10. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **comprehensive rate limiting system** that protects the API from abuse while allowing legitimate usage. Rate limits are:

- **Plan-based** - Different limits for Free, Pro, Team, Enterprise plans
- **Feature-aware** - Different limits for API requests, billing, search, export
- **Endpoint-aware** - Different limits for read, write, delete operations
- **Time-windowed** - Burst (1 minute), sustained (1 hour), daily (24 hours)
- **Fail-closed** - Denies requests if Redis unavailable

### Key Features

- ✅ **Identity-aware** - Limits based on user/admin/anonymous
- ✅ **Billing-aware** - Limits based on subscription plan
- ✅ **Feature-aware** - Limits per feature (API, billing, search, export)
- ✅ **Endpoint-aware** - Limits per operation type (read, write, delete)
- ✅ **Multi-window** - Burst, sustained, and daily limits
- ✅ **Redis-backed** - Scalable across multiple workers
- ✅ **Audit logging** - All rate limit events logged
- ✅ **Abuse detection** - Automatic detection of abuse patterns

---

## Rate Limit Model

### Components

A rate limit is defined by:

1. **Actor Type** - `system`, `admin`, `user`, `anonymous`
2. **Billing Plan** - `free`, `pro`, `team`, `enterprise`
3. **Feature** - `api_requests`, `billing`, `search`, `export`
4. **Endpoint Class** - `read`, `write`, `delete`
5. **Limit Type** - `burst`, `sustained`, `daily`

### Limit Structure

```python
RATE_LIMITS = {
    "free": {
        "api_requests": {
            "read": {"burst": 10000, "sustained": 100000, "daily": 1000000},
            "write": {"burst": 5000, "sustained": 50000, "daily": 500000},
            "delete": {"burst": 2000, "sustained": 10000, "daily": 100000},
        },
        "billing": {
            "read": {"burst": 1000, "sustained": 10000, "daily": 100000},
            "write": {"burst": 500, "sustained": 5000, "daily": 50000},
        },
        # ... more features
    },
    "pro": {
        # ... pro plan limits
    },
    # ... more plans
}
```

### Actor Types

1. **System** (`actor_type="system"`)
   - Internal system operations
   - Highest limits (10,000+ burst)
   - Background jobs, CLI commands

2. **Admin** (`actor_type="admin"`)
   - Admin users
   - High limits (1,000+ burst)
   - Admin operations

3. **User** (`actor_type="user"`)
   - Regular users
   - Limits based on billing plan
   - Free/Pro/Team/Enterprise

4. **Anonymous** (`actor_type="anonymous"`)
   - Unauthenticated requests
   - IP-based identification
   - Lower limits (10,000 burst for testing)

---

## Limit Types

### 1. Burst Limit (1 minute)

**Purpose:** Prevent short-term spikes

**Window:** 1 minute (60 seconds)

**Example:**
- Free plan: 10,000 requests/minute
- Pro plan: 200 requests/minute

**Use Case:** Prevents DDoS attacks and rapid-fire requests

### 2. Sustained Limit (1 hour)

**Purpose:** Prevent sustained abuse

**Window:** 1 hour (3,600 seconds)

**Example:**
- Free plan: 100,000 requests/hour
- Pro plan: 10,000 requests/hour

**Use Case:** Prevents long-running abuse campaigns

### 3. Daily Limit (24 hours)

**Purpose:** Prevent excessive daily usage

**Window:** 24 hours (86,400 seconds)

**Example:**
- Free plan: 1,000,000 requests/day
- Pro plan: 100,000 requests/day

**Use Case:** Prevents resource exhaustion over long periods

### Evaluation Order

**All three limits are checked:**
1. **Burst limit** checked first (1 minute window)
2. **Sustained limit** checked second (1 hour window)
3. **Daily limit** checked third (24 hour window)

**If any limit is exceeded, request is denied (429).**

---

## Plan-Based Limits

### Free Plan

**API Requests:**
- Read: 10,000/min, 100,000/hour, 1,000,000/day
- Write: 5,000/min, 50,000/hour, 500,000/day
- Delete: 2,000/min, 10,000/hour, 100,000/day

**Billing:**
- Read: 1,000/min, 10,000/hour, 100,000/day
- Write: 500/min, 5,000/hour, 50,000/day

### Pro Plan

**API Requests:**
- Read: 200/min, 10,000/hour, 100,000/day
- Write: 100/min, 5,000/hour, 50,000/day
- Delete: 50/min, 1,000/hour, 10,000/day

**Billing:**
- Read: 50/min, 1,000/hour, 10,000/day
- Write: 20/min, 500/hour, 5,000/day

### Team Plan

**API Requests:**
- Read: 500/min, 50,000/hour, 500,000/day
- Write: 200/min, 20,000/hour, 200,000/day
- Delete: 100/min, 5,000/hour, 50,000/day

### Enterprise Plan

**API Requests:**
- Read: 1,000/min, 100,000/hour, 1,000,000/day
- Write: 500/min, 50,000/hour, 500,000/day
- Delete: 200/min, 10,000/hour, 100,000/day

### Admin Plan

**API Requests:**
- Read: 1,000/min, 100,000/hour, 1,000,000/day
- Write: 500/min, 50,000/hour, 500,000/day
- Delete: 200/min, 10,000/hour, 100,000/day

**Note:** Admin users have high limits for system administration.

---

## Rate Limit Algorithm

### Sliding Window

SwX-API uses a **sliding window algorithm** with Redis sorted sets:

```
1. Remove expired entries (older than window)
2. Count current requests in window
3. Add current request
4. Set expiration on key
5. Check if count < limit
```

### Redis Implementation

**Key Format:**
```
rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:{window}
```

**Example:**
```
rate_limit:user:123:api_requests:read:1m
rate_limit:user:123:api_requests:read:1h
rate_limit:user:123:api_requests:read:24h
```

**Data Structure:**
- Redis sorted set (ZSET)
- Timestamps as scores
- Request IDs as members

**Operations:**
```python
# Remove expired entries
ZREMRANGEBYSCORE key 0 window_start

# Count current requests
ZCARD key

# Add current request
ZADD key timestamp timestamp

# Set expiration
EXPIRE key window_seconds
```

### Atomic Operations

**All operations are atomic** using Redis pipelines:

```python
pipe = redis.pipeline()
pipe.zremrangebyscore(key, 0, window_start)
pipe.zcard(key)
pipe.zadd(key, {str(now): now})
pipe.expire(key, window_seconds)
results = await pipe.execute()
```

**Guarantees:**
- Thread-safe across multiple workers
- No race conditions
- Accurate counting

---

## Skip Paths

### What Are Skip Paths?

**Skip paths** are endpoints that bypass rate limiting entirely.

### Default Skip Paths

```python
skip_paths = [
    "/api/utils/health-check",
    "/api/utils/health",
    "/api/utils/language",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/admin/auth",
    "/api/auth",
    "/api/admin/",
    "/api/user/profile",
    "/api/qa_article",
    "/api/oauth",
    "/",
]
```

### Why Skip Paths?

1. **Health Checks** - Must always be available
2. **Authentication** - Users need to login
3. **Admin Endpoints** - Admin users have high limits anyway
4. **Documentation** - OpenAPI docs should be accessible

### Customizing Skip Paths

**In middleware:**
```python
from swx_core.middleware.rate_limit_middleware import RateLimitMiddleware

app.add_middleware(
    RateLimitMiddleware,
    skip_paths=[
        "/api/custom/path",
        "/api/another/path",
    ]
)
```

---

## Usage Examples

### Rate Limit Headers

**Response Headers:**
```
X-RateLimit-Limit: 10000
X-RateLimit-Remaining: 9999
X-RateLimit-Reset: 1706284800
Retry-After: 60
```

### Rate Limit Exceeded Response

**Status Code:** `429 Too Many Requests`

**Response Body:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded for api_requests:read",
  "limit": 10000,
  "remaining": 0,
  "reset_at": "2026-01-26T12:00:00Z",
  "retry_after": 60
}
```

### Client Handling

**Retry Logic:**
```python
import time
import httpx

def make_request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        response = httpx.get(url)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                continue
            else:
                raise Exception("Rate limit exceeded")
        
        return response.json()
```

### Checking Rate Limits

**Get current usage:**
```python
from swx_core.services.rate_limit import get_rate_limiter, LimitWindow

limiter = get_rate_limiter()
key = "rate_limit:user:123:api_requests:read:1m"
usage = await limiter.get_usage(key, LimitWindow.MINUTE)
print(f"Current usage: {usage}/10000")
```

---

## Abuse Detection

### Abuse Patterns

The system detects:

1. **Burst Abuse** - Rapid-fire requests exceeding burst limit
2. **Credential Stuffing** - Multiple failed login attempts
3. **Endpoint Scanning** - Systematic exploration of endpoints
4. **Token Abuse** - Excessive token usage

### Abuse Detection Flow

```
1. Rate limit exceeded
   └── Check for burst abuse

2. Multiple failures
   └── Check for credential stuffing

3. Unusual patterns
   └── Check for endpoint scanning

4. Trigger alerts
   └── Audit log + Alert engine
```

### Abuse Response

**Actions:**
- Audit log entry
- Alert triggered
- Temporary ban (optional)
- IP blocking (optional)

---

## Operational Tuning

### Adjusting Limits

**Update limit registry:**
```python
# swx_core/services/rate_limit/limit_registry.py

RATE_LIMITS["free"]["api_requests"]["read"]["burst"] = 20000
```

**Or via runtime settings:**
```python
# Future: limits in database
await settings_service.set("rate_limit.free.read.burst", "20000")
```

### Monitoring

**Key Metrics:**
- Rate limit exceeded count
- Average requests per user
- Peak usage times
- Most limited features

**Queries:**
```sql
-- Rate limit events
SELECT COUNT(*) 
FROM audit_log 
WHERE action = 'rate_limit.exceeded'
AND created_at > NOW() - INTERVAL '1 hour';

-- Most limited users
SELECT actor_id, COUNT(*) as violations
FROM audit_log
WHERE action = 'rate_limit.exceeded'
GROUP BY actor_id
ORDER BY violations DESC
LIMIT 10;
```

### Tuning Guidelines

1. **Start Conservative** - Lower limits initially
2. **Monitor Usage** - Track actual usage patterns
3. **Adjust Gradually** - Increase limits based on data
4. **Test Changes** - Verify limits work as expected
5. **Document Changes** - Keep track of limit adjustments

---

## Troubleshooting

### Common Issues

**1. "Rate limit exceeded" for legitimate users**
- Check if limits are too restrictive
- Verify user's billing plan
- Check if user is hitting multiple limits
- Review usage patterns

**2. Redis connection errors**
- Verify Redis is running
- Check Redis connection settings
- Verify network connectivity
- Check Redis logs

**3. Limits not applying**
- Verify middleware is loaded
- Check skip_paths configuration
- Verify Redis is working
- Check limit registry configuration

**4. Inconsistent limits across workers**
- Verify Redis is shared across workers
- Check Redis connection pooling
- Verify atomic operations are working
- Check for Redis replication lag

### Debugging

**Enable debug logging:**
```python
import logging
logging.getLogger("swx_core.middleware.rate_limit_middleware").setLevel(logging.DEBUG)
```

**Check Redis keys:**
```bash
redis-cli
KEYS rate_limit:*
ZRANGE rate_limit:user:123:api_requests:read:1m 0 -1 WITHSCORES
```

**Check rate limit status:**
```python
from swx_core.services.rate_limit import get_rate_limiter, LimitWindow

limiter = get_rate_limiter()
key = "rate_limit:user:123:api_requests:read:1m"
usage = await limiter.get_usage(key, LimitWindow.MINUTE)
print(f"Usage: {usage}")
```

---

## Best Practices

### ✅ DO

1. **Set appropriate limits**
   ```python
   # ✅ Good - Based on actual usage
   "read": {"burst": 1000, "sustained": 10000, "daily": 100000}
   
   # ❌ Bad - Too restrictive
   "read": {"burst": 10, "sustained": 100, "daily": 1000}
   ```

2. **Monitor rate limit events**
   ```python
   # Track rate limit violations
   # Alert on unusual patterns
   # Adjust limits based on data
   ```

3. **Provide clear error messages**
   ```python
   # ✅ Good
   {
       "error": "rate_limit_exceeded",
       "retry_after": 60,
       "reset_at": "2026-01-26T12:00:00Z"
   }
   ```

4. **Use skip paths wisely**
   ```python
   # ✅ Good - Skip health checks
   skip_paths = ["/api/utils/health"]
   
   # ❌ Bad - Skip too many paths
   skip_paths = ["/api/*"]  # Defeats purpose
   ```

### ❌ DON'T

1. **Don't set limits too high**
   ```python
   # ❌ Bad - No protection
   "read": {"burst": 999999999, "sustained": 999999999, "daily": 999999999}
   ```

2. **Don't ignore Redis failures**
   ```python
   # ❌ Bad - Fail open
   if not redis:
       return allowed=True
   
   # ✅ Good - Fail closed
   if not redis:
       return allowed=False
   ```

3. **Don't skip rate limiting on critical paths**
   ```python
   # ❌ Bad - Skip billing endpoints
   skip_paths = ["/api/billing/*"]
   
   # ✅ Good - Rate limit billing
   # (billing has separate, appropriate limits)
   ```

---

## Next Steps

- Read [Billing Documentation](./BILLING.md) for plan management
- Read [Audit Logs Documentation](./AUDIT_LOGS.md) for rate limit logging
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Rate limiting documented, ready for implementation.
