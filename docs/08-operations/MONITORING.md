# Monitoring Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Health Checks](#health-checks)
3. [Application Metrics](#application-metrics)
4. [Infrastructure Metrics](#infrastructure-metrics)
5. [Logging](#logging)
6. [Alerting](#alerting)
7. [Monitoring Tools](#monitoring-tools)
8. [Best Practices](#best-practices)

---

## Overview

SwX-API includes **comprehensive monitoring** capabilities including health checks, metrics, logging, and alerting. This guide covers monitoring setup, configuration, and best practices.

### Monitoring Components

- ✅ **Health Checks** - Service health monitoring
- ✅ **Application Metrics** - Request rates, response times, errors
- ✅ **Infrastructure Metrics** - CPU, memory, disk, network
- ✅ **Logging** - Structured logs with audit trails
- ✅ **Alerting** - Multi-channel alerts (Slack, Email, SMS)

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

**Monitoring Health Checks:**
```bash
# Check service health
docker compose ps

# Check health status
docker inspect --format='{{.State.Health.Status}}' swx-api-swx-api-1

# Monitor health checks
watch -n 1 'docker compose ps'
```

---

## Application Metrics

### Key Metrics

**Request Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (errors/second)
- Success rate (successful requests / total requests)

**Authentication Metrics:**
- Login attempts (successful/failed)
- Token refresh rate
- Token expiration rate
- Password reset requests

**Authorization Metrics:**
- Permission checks (allowed/denied)
- Policy evaluations (allowed/denied)
- Rate limit violations
- Access denied events

**Business Metrics:**
- User registrations
- Active users
- API usage by endpoint
- Billing events

### Metrics Collection

**Via Audit Logs:**
```sql
-- Request rate
SELECT COUNT(*) as requests_per_minute
FROM audit_log
WHERE created_at > NOW() - INTERVAL '1 minute';

-- Error rate
SELECT COUNT(*) as errors_per_minute
FROM audit_log
WHERE outcome = 'failure'
AND created_at > NOW() - INTERVAL '1 minute';

-- Authentication failures
SELECT COUNT(*) as failed_logins
FROM audit_log
WHERE action = 'auth.login'
AND outcome = 'failure'
AND created_at > NOW() - INTERVAL '1 hour';
```

**Via Application Logs:**
```bash
# Parse logs for metrics
docker compose logs swx-api | grep ERROR | wc -l

# Count requests
docker compose logs swx-api | grep "GET /api" | wc -l
```

---

## Infrastructure Metrics

### Docker Metrics

**Container Stats:**
```bash
# Real-time stats
docker stats

# Specific container
docker stats swx-api-swx-api-1

# Export stats
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

**Service Health:**
```bash
# Check all services
docker compose ps

# Check specific service
docker compose ps swx-api

# Check resource usage
docker stats $(docker compose ps -q)
```

### System Metrics

**CPU Usage:**
```bash
# System CPU
top

# Container CPU
docker stats --format "{{.CPUPerc}}"
```

**Memory Usage:**
```bash
# System memory
free -h

# Container memory
docker stats --format "{{.MemUsage}}"
```

**Disk Usage:**
```bash
# System disk
df -h

# Docker volumes
docker system df -v
```

**Network Usage:**
```bash
# Network stats
docker stats --format "{{.NetIO}}"
```

### Database Metrics

**Connection Count:**
```sql
SELECT COUNT(*) as active_connections
FROM pg_stat_activity
WHERE datname = 'swx_api';
```

**Query Performance:**
```sql
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

**Database Size:**
```sql
SELECT 
    pg_size_pretty(pg_database_size('swx_api')) as database_size;
```

### Redis Metrics

**Memory Usage:**
```bash
docker compose exec redis redis-cli INFO memory
```

**Key Count:**
```bash
docker compose exec redis redis-cli DBSIZE
```

**Connection Count:**
```bash
docker compose exec redis redis-cli INFO clients
```

---

## Logging

### Log Levels

**Available Levels:**
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
# View logs
docker compose logs swx-api

# Follow logs
docker compose logs -f swx-api

# Export logs
docker compose logs swx-api > api.log
```

**Application Logs:**
- Standard output (captured by Docker)
- Structured JSON logs (if configured)
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

## Alerting

### Alert Channels

**Slack:**
```bash
# Configure Slack webhook
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Email:**
```bash
# Configure SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@yourdomain.com
SMTP_PASSWORD=your-smtp-password
ALERT_EMAIL_TO=ops@yourdomain.com
```

**SMS:**
```bash
# Configure Twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890
ALERT_SMS_TO=+1234567890
```

### Alert Types

**Critical Alerts:**
- Database connection failures
- Service health check failures
- High error rates
- Security breaches

**Warning Alerts:**
- Rate limit violations
- Authentication failures
- High memory usage
- Slow response times

**Info Alerts:**
- Service restarts
- Configuration changes
- Deployment events

### Alert Configuration

**Via Settings:**
```python
# Runtime settings (database)
# Alert thresholds configurable via settings
```

**Via Code:**
```python
# Emit alerts
await alert_engine.emit(
    severity=AlertSeverity.CRITICAL,
    source=AlertSource.INFRA,
    event_type="DATABASE_CONNECTION_LOST",
    message="Database connection lost",
    ...
)
```

---

## Monitoring Tools

### Application Monitoring

**Sentry (Error Tracking):**
```bash
# Configure Sentry
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

**Custom Metrics:**
- Health check endpoints
- Audit log queries
- Application logs

### Infrastructure Monitoring

**Docker Stats:**
```bash
# Real-time monitoring
docker stats

# Export metrics
docker stats --no-stream --format json
```

**System Monitoring:**
- `top` - CPU and memory
- `htop` - Interactive system monitor
- `iotop` - I/O monitoring
- `nethogs` - Network monitoring

### Log Aggregation

**ELK Stack:**
- Elasticsearch (search)
- Logstash (processing)
- Kibana (visualization)

**Loki:**
- Grafana Loki (log aggregation)
- Promtail (log collection)
- Grafana (visualization)

**Cloud Services:**
- AWS CloudWatch
- Google Cloud Logging
- Azure Monitor

---

## Best Practices

### ✅ DO

1. **Monitor health checks**
   ```bash
   # ✅ Good - Monitor health endpoints
   curl http://localhost:8001/api/utils/health-check
   ```

2. **Set up alerting**
   ```python
   # ✅ Good - Alert on critical events
   await alert_engine.emit(
       severity=AlertSeverity.CRITICAL,
       ...
   )
   ```

3. **Monitor key metrics**
   ```sql
   -- ✅ Good - Monitor error rate
   SELECT COUNT(*) FROM audit_log
   WHERE outcome = 'failure'
   AND created_at > NOW() - INTERVAL '1 hour';
   ```

4. **Log important events**
   ```python
   # ✅ Good - Log security events
   await audit.log_event(
       action="auth.login",
       outcome=AuditOutcome.SUCCESS,
       ...
   )
   ```

5. **Use structured logging**
   ```python
   # ✅ Good - Structured logs
   logger.info("User login", extra={"user_id": user.id, "ip": request.client.host})
   ```

### ❌ DON'T

1. **Don't ignore alerts**
   ```python
   # ❌ Bad - Alerts ignored
   # No alerting configured
   
   # ✅ Good - Alerts configured
   await alert_engine.emit(...)
   ```

2. **Don't log sensitive data**
   ```python
   # ❌ Bad - Sensitive data in logs
   logger.info(f"User login: {email}, password: {password}")
   
   # ✅ Good - No sensitive data
   logger.info(f"User login: {email}")
   ```

3. **Don't skip health checks**
   ```bash
   # ❌ Bad - No health checks
   # Health check endpoints not monitored
   
   # ✅ Good - Health checks monitored
   curl http://localhost:8001/api/utils/health-check
   ```

---

## Next Steps

- Read [Operations Guide](./OPERATIONS.md) for day-to-day operations
- Read [Deployment Guide](./DEPLOYMENT.md) for deployment procedures
- Read [Production Checklist](./PRODUCTION_CHECKLIST.md) for production readiness

---

**Status:** Monitoring guide documented, ready for implementation.
