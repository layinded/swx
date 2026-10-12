# Operations Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Infrastructure Components](#infrastructure-components)
3. [Service Management](#service-management)
4. [Health Checks](#health-checks)
5. [Logging](#logging)
6. [Monitoring](#monitoring)
7. [Backup & Recovery](#backup--recovery)
8. [Scaling](#scaling)
9. [Maintenance](#maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API is designed for **production operations** with Docker, health checks, monitoring, and automated deployment. This guide covers day-to-day operations, monitoring, and maintenance.

### Key Operational Features

- ✅ **Docker-based deployment** - Containerized services
- ✅ **Health checks** - Automatic service health monitoring
- ✅ **Logging** - Structured logging with audit trails
- ✅ **Monitoring** - Alerting and metrics
- ✅ **Backup & Recovery** - Database backups and restore
- ✅ **Scaling** - Horizontal scaling support

---

## Infrastructure Components

### Service Architecture

**Core Services:**
1. **swx-api** - FastAPI application
2. **db** - PostgreSQL/TimescaleDB database
3. **redis** - Redis cache and rate limiting
4. **vectorizer-worker** - AI vectorization worker (optional)
5. **caddy** - Reverse proxy and TLS termination (production)

### Service Dependencies

```
swx-api
├── db (PostgreSQL)
├── redis (Redis)
└── vectorizer-worker (optional)

caddy
└── swx-api (reverse proxy)
```

### Network Architecture

**Docker Network:**
- Default network: `swx-api-network`
- Services communicate via service names
- Internal communication only (not exposed)

**Port Mapping:**
- `8001:8000` - API service (development)
- `5432:5432` - Database (if exposed)
- `6379:6379` - Redis (if exposed)
- `443:443` - HTTPS (production, via Caddy)
- `80:80` - HTTP (production, via Caddy)

---

## Service Management

### Starting Services

**Development:**
```bash
# Start all services
docker compose up -d

# Start specific service
docker compose up -d swx-api

# Start with logs
docker compose up
```

**Production:**
```bash
# Start production services
docker compose -f docker-compose.production.yml up -d --build

# Start with specific configuration
docker compose -f docker-compose.production.yml up -d
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Stop specific service
docker compose stop swx-api
```

### Restarting Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart swx-api

# Restart with rebuild
docker compose up -d --build
```

### Viewing Logs

```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs swx-api

# Follow logs (real-time)
docker compose logs -f swx-api

# View last 100 lines
docker compose logs --tail=100 swx-api
```

### Service Status

```bash
# Check service status
docker compose ps

# Check service health
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
```

---

## Health Checks

### Health Check Endpoints

**Basic Health Check:**
```bash
GET /api/utils/health-check
```

**Response:**
```json
{
  "status": "healthy",
  "service": "swx-api"
}
```

**Detailed Health Check:**
```bash
GET /api/utils/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "swx-api",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2026-01-26T12:00:00Z"
}
```

### Docker Health Checks

**Service Health Checks:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/utils/health-check"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 40s
```

**Database Health Check:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
  interval: 10s
  retries: 5
  start_period: 30s
```

**Redis Health Check:**
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 5s
  retries: 5
```

### Health Check Monitoring

**Manual Check:**
```bash
# Check API health
curl http://localhost:8001/api/utils/health-check

# Check detailed health
curl http://localhost:8001/api/utils/health
```

**Automated Monitoring:**
- Docker health checks run automatically
- External monitoring tools can poll health endpoints
- Alerting configured for health check failures

---

## Logging

### Log Levels

**Available Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

### Log Configuration

**Environment Variables:**
```bash
LOG_LEVEL=INFO  # Set log level
ENVIRONMENT=production  # Environment name
```

### Log Locations

**Docker Logs:**
```bash
# View container logs
docker compose logs swx-api

# Follow logs
docker compose logs -f swx-api

# Export logs
docker compose logs swx-api > api.log
```

**Application Logs:**
- Structured JSON logs (if configured)
- Standard output (captured by Docker)
- Audit logs in database (`audit_log` table)

### Log Analysis

**Filter Logs:**
```bash
# Filter by level
docker compose logs swx-api | grep ERROR

# Filter by time
docker compose logs --since 1h swx-api

# Filter by service
docker compose logs swx-api db redis
```

**Log Aggregation:**
- Use log aggregation tools (ELK, Loki, etc.)
- Forward logs to centralized logging service
- Monitor logs for errors and anomalies

---

## Monitoring

### Key Metrics

**Application Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (errors/second)
- Active users
- Token refresh rate

**Infrastructure Metrics:**
- CPU usage
- Memory usage
- Disk I/O
- Network I/O
- Database connections

**Business Metrics:**
- User registrations
- Login attempts
- API usage by endpoint
- Rate limit violations
- Billing events

### Monitoring Tools

**Application Monitoring:**
- Sentry (error tracking)
- Custom metrics endpoints
- Health check endpoints
- Audit logs

**Infrastructure Monitoring:**
- Docker stats
- System metrics (CPU, memory, disk)
- Database metrics
- Redis metrics

### Alerting

**Alert Channels:**
- Slack (real-time notifications)
- Email (critical alerts)
- SMS (critical alerts)
- Logs (all alerts)

**Alert Types:**
- Health check failures
- High error rates
- Rate limit violations
- Database connection failures
- Authentication failures

---

## Backup & Recovery

### Database Backups

**Manual Backup:**
```bash
# Backup database
docker compose exec db pg_dump -U ${DB_USER} ${DB_NAME} > backup.sql

# Backup with timestamp
docker compose exec db pg_dump -U ${DB_USER} ${DB_NAME} > backup-$(date +%Y%m%d-%H%M%S).sql
```

**Automated Backups:**
```bash
# Cron job for daily backups
0 2 * * * docker compose exec -T db pg_dump -U ${DB_USER} ${DB_NAME} > /backups/backup-$(date +\%Y\%m\%d).sql
```

**Backup Storage:**
- Store backups in secure location
- Encrypt backups
- Test restore procedures regularly
- Keep multiple backup copies

### Database Restore

**Restore from Backup:**
```bash
# Restore database
docker compose exec -T db psql -U ${DB_USER} ${DB_NAME} < backup.sql

# Restore with drop
docker compose exec db psql -U ${DB_USER} -c "DROP DATABASE ${DB_NAME};"
docker compose exec db psql -U ${DB_USER} -c "CREATE DATABASE ${DB_NAME};"
docker compose exec -T db psql -U ${DB_USER} ${DB_NAME} < backup.sql
```

### Redis Backups

**Redis Persistence:**
- AOF (Append-Only File) enabled
- Automatic persistence to disk
- Backup Redis data directory

**Backup Redis:**
```bash
# Backup Redis data
docker compose exec redis redis-cli SAVE
docker compose cp redis:/data/dump.rdb ./redis-backup.rdb
```

---

## Scaling

### Horizontal Scaling

**API Service Scaling:**
```bash
# Scale API service
docker compose up -d --scale swx-api=3

# Scale with load balancer
# Use reverse proxy (Caddy, nginx) for load balancing
```

**Database Scaling:**
- Use read replicas for read-heavy workloads
- Use connection pooling
- Monitor connection counts

**Redis Scaling:**
- Use Redis Cluster for high availability
- Use Redis Sentinel for failover
- Monitor memory usage

### Vertical Scaling

**Resource Limits:**
```yaml
services:
  swx-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

**Database Scaling:**
- Increase database memory
- Add more CPU cores
- Use faster storage (SSD)

---

## Maintenance

### Database Migrations

**Run Migrations:**
```bash
# Run migrations
docker compose exec swx-api alembic upgrade head

# Check migration status
docker compose exec swx-api alembic current

# Rollback migration
docker compose exec swx-api alembic downgrade -1
```

**Migration Best Practices:**
- Test migrations in staging first
- Backup database before migrations
- Run migrations during maintenance window
- Monitor migration progress

### System Updates

**Update Application:**
```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Verify health
curl http://localhost:8001/api/utils/health-check
```

**Update Dependencies:**
```bash
# Update dependencies
docker compose exec swx-api pip install --upgrade package-name

# Rebuild image
docker compose up -d --build
```

### Maintenance Windows

**Scheduled Maintenance:**
- Plan maintenance during low-traffic periods
- Notify users in advance
- Have rollback plan ready
- Monitor during maintenance

---

## Troubleshooting

### Common Issues

**1. Service Won't Start**
```bash
# Check logs
docker compose logs swx-api

# Check health
docker compose ps

# Check dependencies
docker compose ps db redis
```

**2. Database Connection Errors**
```bash
# Check database status
docker compose ps db

# Check database logs
docker compose logs db

# Test connection
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1;"
```

**3. Redis Connection Errors**
```bash
# Check Redis status
docker compose ps redis

# Check Redis logs
docker compose logs redis

# Test connection
docker compose exec redis redis-cli ping
```

**4. High Memory Usage**
```bash
# Check memory usage
docker stats

# Check specific service
docker stats swx-api

# Restart service
docker compose restart swx-api
```

**5. Slow Performance**
```bash
# Check CPU usage
docker stats

# Check database queries
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT * FROM pg_stat_activity;"

# Check Redis memory
docker compose exec redis redis-cli INFO memory
```

### Debugging

**Enable Debug Logging:**
```bash
# Set debug log level
export LOG_LEVEL=DEBUG

# Restart service
docker compose restart swx-api

# View debug logs
docker compose logs -f swx-api
```

**Database Debugging:**
```bash
# Connect to database
docker compose exec db psql -U ${DB_USER} -d ${DB_NAME}

# Check connections
SELECT * FROM pg_stat_activity;

# Check locks
SELECT * FROM pg_locks;
```

**Redis Debugging:**
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check memory
INFO memory

# Check keys
KEYS *

# Monitor commands
MONITOR
```

---

## Next Steps

- Read [Deployment Guide](./DEPLOYMENT.md) for deployment procedures
- Read [Monitoring Guide](./MONITORING.md) for monitoring setup
- Read [Production Checklist](./PRODUCTION_CHECKLIST.md) for production readiness

---

**Status:** Operations guide documented, ready for implementation.
