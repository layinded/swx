# Troubleshooting Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Common Issues](#common-issues)
3. [Authentication Issues](#authentication-issues)
4. [Database Issues](#database-issues)
5. [Redis Issues](#redis-issues)
6. [Rate Limiting Issues](#rate-limiting-issues)
7. [Performance Issues](#performance-issues)
8. [Deployment Issues](#deployment-issues)
9. [Debugging Tools](#debugging-tools)

---

## Overview

This guide covers **common issues and troubleshooting steps** for SwX-API. Use this guide to diagnose and resolve problems quickly.

### Troubleshooting Process

1. **Identify the Issue** - What's not working?
2. **Check Logs** - Review application and system logs
3. **Verify Configuration** - Check environment variables
4. **Test Components** - Test individual components
5. **Apply Fix** - Implement solution
6. **Verify Fix** - Confirm issue resolved

---

## Common Issues

### Issue 1: Service Won't Start

**Symptoms:**
- Container exits immediately
- Service not responding
- Health checks failing

**Diagnosis:**
```bash
# Check service status
docker compose ps

# Check logs
docker compose logs swx-api

# Check health
curl http://localhost:8001/api/utils/health-check
```

**Common Causes:**
- Database not ready
- Missing environment variables
- Port conflicts
- Configuration errors

**Solutions:**
```bash
# Wait for database
docker compose up -d db
sleep 30

# Check environment
docker compose exec swx-api env | grep DB_

# Check ports
netstat -tuln | grep 8001
```

### Issue 2: Database Connection Failed

**Symptoms:**
- "Database connection failed" errors
- Health check shows database disconnected
- 500 errors on database operations

**Diagnosis:**
```bash
# Check database status
docker compose ps db

# Check database logs
docker compose logs db

# Test connection
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1;"
```

**Common Causes:**
- Database not running
- Wrong credentials
- Network issues
- Database not ready

**Solutions:**
```bash
# Restart database
docker compose restart db

# Check credentials
docker compose exec swx-api env | grep DB_

# Wait for database
sleep 30
```

### Issue 3: Redis Connection Failed

**Symptoms:**
- Rate limiting not working
- Cache errors
- "Redis unavailable" warnings

**Diagnosis:**
```bash
# Check Redis status
docker compose ps redis

# Check Redis logs
docker compose logs redis

# Test connection
docker compose exec redis redis-cli ping
```

**Common Causes:**
- Redis not running
- Wrong credentials
- Network issues

**Solutions:**
```bash
# Restart Redis
docker compose restart redis

# Check credentials
docker compose exec swx-api env | grep REDIS_

# Test connection
docker compose exec redis redis-cli ping
```

---

## Authentication Issues

### Issue: Invalid Token

**Symptoms:**
- 401 Unauthorized errors
- "Invalid or expired token" messages

**Diagnosis:**
```bash
# Check token expiration
# Decode token (for debugging)
python -c "import jwt; print(jwt.decode(token, options={'verify_signature': False}))"
```

**Common Causes:**
- Token expired
- Wrong secret key
- Token audience mismatch
- Token format invalid

**Solutions:**
```bash
# Refresh token
POST /api/auth/refresh

# Re-authenticate
POST /api/auth/

# Check secret key
docker compose exec swx-api env | grep SECRET_KEY
```

### Issue: Login Fails

**Symptoms:**
- 401 on login
- "Incorrect email or password" errors

**Diagnosis:**
```bash
# Check user exists
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT email FROM \"user\" WHERE email = 'user@example.com';"

# Check password hash
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT hashed_password FROM \"user\" WHERE email = 'user@example.com';"
```

**Common Causes:**
- User doesn't exist
- Wrong password
- User inactive
- Password hash mismatch

**Solutions:**
```bash
# Reset password
python scripts/reset_admin_password.py

# Create user
POST /api/admin/user/
```

---

## Database Issues

### Issue: Migration Fails

**Symptoms:**
- Migration errors
- Schema mismatch
- Table not found

**Diagnosis:**
```bash
# Check migration status
docker compose exec swx-api alembic current

# Check migration history
docker compose exec swx-api alembic history

# Check database schema
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "\dt"
```

**Common Causes:**
- Migration not applied
- Migration conflict
- Database schema mismatch

**Solutions:**
```bash
# Apply migrations
docker compose exec swx-api alembic upgrade head

# Rollback migration
docker compose exec swx-api alembic downgrade -1

# Check for conflicts
docker compose exec swx-api alembic check
```

### Issue: Slow Queries

**Symptoms:**
- Slow API responses
- High database CPU
- Timeout errors

**Diagnosis:**
```bash
# Check active queries
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Check slow queries
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

**Common Causes:**
- Missing indexes
- Large tables
- Inefficient queries
- Connection pool exhaustion

**Solutions:**
```bash
# Add indexes
CREATE INDEX idx_user_email ON "user"(email);

# Analyze tables
ANALYZE "user";

# Increase connection pool
# In database configuration
```

---

## Redis Issues

### Issue: Rate Limiting Not Working

**Symptoms:**
- No rate limit enforcement
- "Redis unavailable" warnings
- Rate limits not applied

**Diagnosis:**
```bash
# Check Redis connection
docker compose exec swx-api python -c "import redis; r = redis.Redis(host='redis'); print(r.ping())"

# Check Redis keys
docker compose exec redis redis-cli KEYS "rate_limit:*"

# Check Redis memory
docker compose exec redis redis-cli INFO memory
```

**Common Causes:**
- Redis not running
- Wrong connection settings
- Redis password incorrect
- Network issues

**Solutions:**
```bash
# Restart Redis
docker compose restart redis

# Check configuration
docker compose exec swx-api env | grep REDIS_

# Test connection
docker compose exec redis redis-cli ping
```

### Issue: Cache Not Working

**Symptoms:**
- Cache misses
- Slow responses
- Cache errors

**Diagnosis:**
```bash
# Check Redis keys
docker compose exec redis redis-cli KEYS "*"

# Check Redis memory
docker compose exec redis redis-cli INFO memory
```

**Common Causes:**
- Redis not configured
- Cache TTL too short
- Memory limits

**Solutions:**
```bash
# Increase memory
# In Redis configuration

# Check cache TTL
# In settings service
```

---

## Rate Limiting Issues

### Issue: Too Many Rate Limit Errors

**Symptoms:**
- Frequent 429 errors
- Legitimate users blocked
- Rate limits too restrictive

**Diagnosis:**
```bash
# Check rate limit configuration
# swx_core/services/rate_limit/limit_registry.py

# Check Redis rate limit keys
docker compose exec redis redis-cli KEYS "rate_limit:*"
```

**Common Causes:**
- Limits too low
- Burst abuse
- Redis issues

**Solutions:**
```bash
# Increase limits
# In limit_registry.py

# Clear rate limit keys
docker compose exec redis redis-cli FLUSHALL

# Add skip paths
# In rate_limit_middleware.py
```

### Issue: Rate Limits Not Applied

**Symptoms:**
- No rate limit enforcement
- Unlimited requests
- Rate limit headers missing

**Diagnosis:**
```bash
# Check middleware loaded
docker compose logs swx-api | grep "Rate limit middleware"

# Check Redis connection
docker compose exec redis redis-cli ping
```

**Common Causes:**
- Middleware not loaded
- Redis unavailable
- Skip paths too broad

**Solutions:**
```bash
# Verify middleware
# Check main.py

# Restart service
docker compose restart swx-api
```

---

## Performance Issues

### Issue: Slow API Responses

**Symptoms:**
- High response times
- Timeout errors
- Slow database queries

**Diagnosis:**
```bash
# Check response times
curl -w "@curl-format.txt" http://localhost:8001/api/utils/health-check

# Check database queries
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Check CPU/memory
docker stats
```

**Common Causes:**
- Slow database queries
- Missing indexes
- High load
- Resource constraints

**Solutions:**
```bash
# Add indexes
CREATE INDEX idx_user_email ON "user"(email);

# Optimize queries
# Review query patterns

# Scale services
docker compose up -d --scale swx-api=3
```

### Issue: High Memory Usage

**Symptoms:**
- Memory warnings
- OOM errors
- Container restarts

**Diagnosis:**
```bash
# Check memory usage
docker stats

# Check container limits
docker inspect swx-api-swx-api-1 | grep Memory
```

**Common Causes:**
- Memory leaks
- Large datasets
- Too many connections

**Solutions:**
```bash
# Increase memory limits
# In docker-compose.yml

# Reduce connection pool
# In database configuration

# Restart service
docker compose restart swx-api
```

---

## Deployment Issues

### Issue: Service Won't Start in Production

**Symptoms:**
- Container exits
- Health checks fail
- Service unavailable

**Diagnosis:**
```bash
# Check logs
docker compose -f docker-compose.production.yml logs swx-api

# Check health
curl https://api.yourdomain.com/api/utils/health-check

# Check DNS
dig api.yourdomain.com
```

**Common Causes:**
- Missing environment variables
- Database not accessible
- DNS not configured
- SSL certificate issues

**Solutions:**
```bash
# Check environment
docker compose -f docker-compose.production.yml exec swx-api env

# Verify DNS
dig api.yourdomain.com

# Check SSL
curl -I https://api.yourdomain.com
```

### Issue: SSL Certificate Errors

**Symptoms:**
- Certificate errors
- HTTPS not working
- Let's Encrypt failures

**Diagnosis:**
```bash
# Check Caddy logs
docker compose logs caddy

# Check certificate
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
```

**Common Causes:**
- DNS not configured
- Domain not accessible
- Rate limiting (Let's Encrypt)

**Solutions:**
```bash
# Verify DNS
dig api.yourdomain.com

# Check Caddyfile
cat Caddyfile

# Restart Caddy
docker compose restart caddy
```

---

## Debugging Tools

### Application Logs

**View Logs:**
```bash
# All services
docker compose logs

# Specific service
docker compose logs swx-api

# Follow logs
docker compose logs -f swx-api

# Last 100 lines
docker compose logs --tail=100 swx-api
```

### Database Debugging

**Connect to Database:**
```bash
# PostgreSQL
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME}

# Run queries
SELECT * FROM "user" LIMIT 10;
SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10;
```

### Redis Debugging

**Connect to Redis:**
```bash
# Redis CLI
docker compose exec redis redis-cli

# Check keys
KEYS *
KEYS rate_limit:*

# Check memory
INFO memory

# Monitor commands
MONITOR
```

### Health Checks

**Check Health:**
```bash
# Basic health
curl http://localhost:8001/api/utils/health-check

# Detailed health
curl http://localhost:8001/api/utils/health

# Service status
docker compose ps
```

---

## Next Steps

- Read [FAQ](./FAQ.md) for common questions
- Read [Debugging Guide](./DEBUGGING.md) for debugging techniques
- Read [Operations Guide](../08-operations/OPERATIONS.md) for operations

---

**Status:** Troubleshooting guide documented, ready for implementation.
