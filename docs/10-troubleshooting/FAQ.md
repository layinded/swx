# Frequently Asked Questions (FAQ)

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [General Questions](#general-questions)
2. [Authentication Questions](#authentication-questions)
3. [Authorization Questions](#authorization-questions)
4. [Database Questions](#database-questions)
5. [Deployment Questions](#deployment-questions)
6. [Performance Questions](#performance-questions)

---

## General Questions

### Q: What is SwX-API?

**A:** SwX-API is a production-ready FastAPI framework for building SaaS applications. It provides authentication, authorization, billing, rate limiting, audit logging, and more out of the box.

### Q: Who is SwX-API for?

**A:** SwX-API is designed for:
- **Platform Engineers** building SaaS platforms
- **Backend Developers** needing production-ready infrastructure
- **Startups** requiring rapid development
- **Enterprises** needing security and compliance

### Q: Is SwX-API production-ready?

**A:** Yes. SwX-API includes:
- Security best practices
- Comprehensive audit logging
- Rate limiting and abuse protection
- Billing and entitlements
- Background jobs
- Monitoring and alerting

### Q: How do I get started?

**A:** See the [Getting Started Guide](../02-getting-started/GETTING_STARTED.md) for installation and setup instructions.

---

## Authentication Questions

### Q: How do I authenticate?

**A:** Use JWT tokens:
1. Login: `POST /api/auth/` with email and password
2. Receive access and refresh tokens
3. Use access token: `Authorization: Bearer <token>`
4. Refresh when expired: `POST /api/auth/refresh`

### Q: What's the difference between admin and user tokens?

**A:** 
- **Admin tokens** (`audience="admin"`) - Access admin endpoints only
- **User tokens** (`audience="user"`) - Access user endpoints only
- Tokens cannot cross domains

### Q: How long do tokens last?

**A:** 
- **Access tokens:** Default 7 days (configurable)
- **Refresh tokens:** Default 30 days (configurable)
- **Password reset tokens:** Default 48 hours (configurable)

### Q: Can I revoke tokens?

**A:** Yes. Refresh tokens can be revoked:
- Single token: `POST /api/auth/logout`
- All tokens: Password reset revokes all tokens

---

## Authorization Questions

### Q: How does RBAC work?

**A:** 
1. **Permissions** are atomic actions (e.g., `"user:read"`)
2. **Roles** are collections of permissions
3. **Users** are assigned roles (global or team-scoped)
4. Routes check permissions before allowing access

### Q: How does the Policy Engine work?

**A:** 
1. Policies evaluate conditions on actors, actions, resources, and context
2. Policies can ALLOW, DENY, or CONDITIONAL_ALLOW
3. DENY takes precedence
4. If no policy matches, default DENY (fail-closed)

### Q: What's the difference between RBAC and Policies?

**A:** 
- **RBAC** - Permission-based (can user do this?)
- **Policies** - Condition-based (under what conditions can user do this?)
- Both are checked - RBAC first, then Policies

### Q: How do I check permissions in code?

**A:** 
```python
from swx_core.rbac.helpers import has_permission

if await has_permission(session, user, "user:delete"):
    # Allow deletion
    ...
```

---

## Database Questions

### Q: How do I run migrations?

**A:** 
```bash
# Apply migrations
alembic upgrade head

# Check status
alembic current

# Rollback
alembic downgrade -1
```

### Q: How do I backup the database?

**A:** 
```bash
# Manual backup
docker compose exec db pg_dump -U ${DB_USER} ${DB_NAME} > backup.sql

# Automated backup
# Set up cron job or backup service
```

### Q: How do I restore the database?

**A:** 
```bash
# Restore from backup
docker compose exec -T db psql -U ${DB_USER} ${DB_NAME} < backup.sql
```

### Q: What database does SwX-API use?

**A:** PostgreSQL with TimescaleDB extension (for time-series data if needed).

---

## Deployment Questions

### Q: How do I deploy to production?

**A:** See the [Deployment Guide](../08-operations/DEPLOYMENT.md) for step-by-step instructions.

### Q: Do I need HTTPS?

**A:** Yes, in production. SwX-API uses Caddy for automatic HTTPS via Let's Encrypt.

### Q: How do I scale the application?

**A:** 
```bash
# Horizontal scaling
docker compose up -d --scale swx-api=3

# Use load balancer (Caddy, nginx)
# Configure in Caddyfile
```

### Q: How do I monitor the application?

**A:** 
- Health checks: `/api/utils/health-check`
- Application logs: `docker compose logs swx-api`
- Audit logs: Database `audit_log` table
- Metrics: Docker stats, database metrics

---

## Performance Questions

### Q: How do I improve performance?

**A:** 
1. **Add indexes** - Index frequently queried fields
2. **Use caching** - Redis for rate limiting and caching
3. **Optimize queries** - Review slow queries
4. **Scale horizontally** - Multiple API instances
5. **Connection pooling** - Tune database connection pool

### Q: How do I find slow queries?

**A:** 
```sql
-- Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

### Q: How do I optimize database performance?

**A:** 
1. Add indexes for common queries
2. Analyze tables regularly
3. Tune connection pool size
4. Use read replicas for read-heavy workloads
5. Monitor query performance

---

## Next Steps

- Read [Troubleshooting Guide](./TROUBLESHOOTING.md) for issue resolution
- Read [Debugging Guide](./DEBUGGING.md) for debugging techniques
- Read [Operations Guide](../08-operations/OPERATIONS.md) for operations

---

**Status:** FAQ documented, ready for implementation.
