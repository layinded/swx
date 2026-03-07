# Security Hardening Guide (SwX v2.0.0)

**Version:** 2.0.0  
**Last Updated:** 2026-02-28

---

## Table of Contents

1. [Scope and Assumptions](#scope-and-assumptions)
2. [Environment Security](#environment-security)
3. [Authentication Hardening](#authentication-hardening)
4. [Authorization Hardening](#authorization-hardening)
5. [Network Security](#network-security)
6. [Database Security](#database-security)
7. [Redis Security](#redis-security)
8. [Logging & Monitoring](#logging--monitoring)
9. [Compliance](#compliance)
10. [Incident Response](#incident-response)

---

## Scope and Assumptions

- This guide is for production deployments of SwX.
- Assume mistakes will be exploited: leaked tokens, weak secrets, permissive CORS, exposed Redis/Postgres, over-privileged roles, and noisy logs.
- Treat availability as a security property: if a security control becomes unavailable (Redis for blacklist/rate limit, policy engine storage, audit logger), prefer denying access over allowing it.

Related docs:

- `docs/05-security/SECRETS_MANAGEMENT.md`
- `docs/05-security/TOKEN_SECURITY.md`
- `docs/04-core-concepts/RBAC.md`
- `docs/04-core-concepts/POLICY_ENGINE.md`
- `docs/04-core-concepts/AUDIT_LOGS.md`
- `docs/04-core-concepts/RATE_LIMITING.md`

---

## Environment Security

### SECRET_KEY generation and management

SwX uses HMAC-signed JWTs by default (`HS256`). If an attacker obtains `SECRET_KEY`, they can mint valid tokens.

Generate secrets offline and inject them at runtime:

```bash
# 64 bytes of randomness (recommended)
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Alternative (base64, no padding requirements)
openssl rand -base64 64
```

Minimum requirements (production):

- Set `SECRET_KEY`, `REFRESH_SECRET_KEY`, and `PASSWORD_RESET_SECRET_KEY` explicitly.
- Use different secrets per environment (local/staging/production) and per deployment (no shared keys across clusters/accounts).
- Store only in your secrets system; never in git, container images, or logs.

Operational rule:

- Missing or auto-generated secrets in production is a failure. If your runtime can start without explicitly-set secrets, treat that as a misconfiguration and block startup via deployment checks.

### Production configuration sanity checks

SwX settings include insecure development defaults (example: `DB_PASSWORD=changeme`, default superuser credentials). In production:

- Set `ENVIRONMENT=production`.
- Remove all default credentials.
- Ensure Redis is enabled when you rely on blacklist/rate limiting.

Minimum environment variables to explicitly set (typical):

```bash
ENVIRONMENT=production

SECRET_KEY=<strong>
REFRESH_SECRET_KEY=<strong>
PASSWORD_RESET_SECRET_KEY=<strong>

DB_HOST=<private-host>
DB_PORT=5432
DB_USER=swx_user
DB_PASSWORD=<strong>
DB_NAME=swx_db

REDIS_ENABLED=true
REDIS_HOST=<private-host>
REDIS_PORT=6379
REDIS_PASSWORD=<strong>
REDIS_DB=0

FIRST_SUPERUSER=<admin-email>
FIRST_SUPERUSER_PASSWORD=<strong>
BACKEND_CORS_ORIGINS=https://app.example.com
```

### Environment variable security

Common failure modes:

- Secrets visible via process env to other users/processes.
- Secrets dumped into crash logs.
- `.env` readable by other accounts on the host.

Hard requirements:

- File permissions (if you must use `.env`):

```bash
chmod 600 .env
chown <service-user>:<service-user> .env
```

- Do not print environment variables in diagnostics in production. Avoid `print(os.environ)` or equivalent.
- Do not include secrets in exception messages.

Systemd example (non-root, restrict the process):

```ini
# /etc/systemd/system/swx.service
[Service]
User=swx
Group=swx
EnvironmentFile=/etc/swx/swx.env

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictSUIDSGID=true

UMask=0077
ExecStart=/usr/bin/uvicorn swx_core.main:app --host 0.0.0.0 --port 8001
```

Container/Kubernetes guidance:

- Prefer mounted secrets (tmpfs) over environment variables when possible.
- Never bake secrets into images.
- Deny shell access to production app containers by default.

### Secrets storage (Vault, AWS Secrets Manager)

HashiCorp Vault (KV v2) example:

```bash
vault kv put kv/swx/production \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  REFRESH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  PASSWORD_RESET_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  DB_PASSWORD="<rotate-me>" \
  REDIS_PASSWORD="<rotate-me>"
```

Vault Agent template example (render to file, read by process):

```hcl
# /etc/vault-agent.d/swx.hcl
template {
  source      = "/etc/vault-agent.d/templates/swx.env.tmpl"
  destination = "/run/secrets/swx.env"
  perms       = "0400"
}
```

```text
# /etc/vault-agent.d/templates/swx.env.tmpl
SECRET_KEY={{ with secret "kv/data/swx/production" }}{{ .Data.data.SECRET_KEY }}{{ end }}
REFRESH_SECRET_KEY={{ with secret "kv/data/swx/production" }}{{ .Data.data.REFRESH_SECRET_KEY }}{{ end }}
PASSWORD_RESET_SECRET_KEY={{ with secret "kv/data/swx/production" }}{{ .Data.data.PASSWORD_RESET_SECRET_KEY }}{{ end }}
DB_PASSWORD={{ with secret "kv/data/swx/production" }}{{ .Data.data.DB_PASSWORD }}{{ end }}
REDIS_PASSWORD={{ with secret "kv/data/swx/production" }}{{ .Data.data.REDIS_PASSWORD }}{{ end }}
```

AWS Secrets Manager example:

```bash
aws secretsmanager create-secret \
  --name swx/production/app \
  --secret-string '{"SECRET_KEY":"<...>","REFRESH_SECRET_KEY":"<...>","PASSWORD_RESET_SECRET_KEY":"<...>"}'

aws secretsmanager get-secret-value --secret-id swx/production/app --query SecretString --output text
```

Rules:

- Restrict who can read secrets (human and machine identities).
- Log every secret read (Vault audit logs / CloudTrail) and alert on unusual access.
- Rotate secrets on a schedule and on any suspected compromise.

### Environment isolation

Isolation failures are breach multipliers.

- Separate accounts/projects for staging vs production.
- Separate VPC/VNet/subnets; do not allow staging to reach production networks.
- Separate databases and Redis instances per environment.
- Separate OAuth app registrations and redirect URIs per environment.
- Separate audit log sinks per environment (do not mix prod logs into shared dev indices).

---

## Authentication Hardening

### JWT security best practices

Hard requirements (production):

- Use strong secrets (see Environment Security).
- Pin the algorithm (`HS256`) and never accept `none`.
- Validate token audience (`aud`) on every request.
- Include and validate time-based claims: `exp` (required), `iat` (recommended).
- Do not store secrets, passwords, or PII in JWT payloads.
- Treat JWTs as bearer credentials: anyone who has one can use it.

SwX guard notes:

- `swx_core/guards/jwt_guard.py` includes `jti` and `iat` on issued tokens.
- The guard supports blacklist checks and can fail closed.

### Token expiration policies

Defaults are often too long for hostile environments. Prefer short access tokens and revocable refresh tokens.

Recommended starting points:

- Access token: 10-30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token: 7-30 days (`REFRESH_TOKEN_EXPIRE_DAYS`)
- Password reset token: 30-120 minutes (`EMAIL_RESET_TOKEN_EXPIRE_HOURS`)

Set via environment:

```bash
# Example production policy
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
EMAIL_RESET_TOKEN_EXPIRE_HOURS=2
```

Rules:

- Shorten lifetimes when:
  - High-value admin operations exist.
  - You cannot guarantee client device security.
  - You have weak session controls (no device binding).
- Enforce server time correctness (NTP). Clock drift breaks expiry.

### Token blacklist implementation

Stateless access tokens require an explicit revocation mechanism if you need immediate invalidation.

SwX provides a Redis-backed blacklist:

- Interface and implementations: `swx_core/security/token_blacklist.py`
- Guard integration: `swx_core/guards/jwt_guard.py`

Operational requirements:

- Use `RedisTokenBlacklist` in production.
- Co-locate Redis near API workers to reduce latency.
- Treat blacklist unavailability as an authentication failure (fail closed).

Example wiring (conceptual):

```python
import redis.asyncio as aioredis
from swx_core.guards.jwt_guard import JWTGuard
from swx_core.security.token_blacklist import RedisTokenBlacklist
from swx_core.config.settings import settings

redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
blacklist = RedisTokenBlacklist(redis)

guard = JWTGuard(
    secret_key=settings.SECRET_KEY,
    token_blacklist=blacklist,
    strict_blacklist=True,
)
```

Revocation patterns:

- Revoke a single token (logout): store `jti` with TTL until `exp`.
- Revoke all tokens for a user (account compromise): store a per-user `revoked_at` timestamp; reject tokens with `iat < revoked_at`.

### Fail-closed security patterns

Fail-open patterns are how token revocation and rate limiting get bypassed during outages.

- If Redis is required for revocation, and Redis is unreachable, deny authentication.
- If policy evaluation cannot complete, deny access.
- If audit logging cannot write, do not drop the event silently; at minimum, emit a high-severity operational alert.

SwX examples:

- `JWTGuard(..., strict_blacklist=True)` denies tokens when blacklist cannot be checked.
- Rate limiting is documented as fail-closed; verify your deployment keeps it that way.

### Rate limiting on auth endpoints

Credential stuffing and brute-force attacks target:

- Login
- Token refresh
- Password reset
- OAuth callback endpoints

Minimum controls:

- IP-based throttling for anonymous attempts.
- Account-based throttling for known identifiers (email/username), even if the account does not exist.
- Progressive delays (increasing wait on repeated failures).
- Lockout only with careful design (attackers can lock out victims).

SwX note:

- The default middleware skip list includes `/api/auth` and `/api/admin/auth` (`swx_core/middleware/rate_limit_middleware.py`). For production, remove auth endpoints from skip paths and apply strict, dedicated limits.

Example: explicitly configure middleware with a reduced skip list (do not skip auth):

```python
from fastapi import FastAPI
from swx_core.middleware.rate_limit_middleware import RateLimitMiddleware

app = FastAPI()

app.add_middleware(
    RateLimitMiddleware,
    skip_paths=[
        "/api/utils/health-check",
        "/api/utils/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ],
)
```

Edge throttling example (Nginx), independent of app logic:

```nginx
limit_req_zone $binary_remote_addr zone=auth_zone:10m rate=5r/s;

location = /api/auth {
    limit_req zone=auth_zone burst=10 nodelay;
    proxy_pass http://swx_api:8001;
}

location = /api/admin/auth {
    limit_req zone=auth_zone burst=5 nodelay;
    proxy_pass http://swx_api:8001;
}
```

---

## Authorization Hardening

### RBAC best practices

Follow the permission-first model (`docs/04-core-concepts/RBAC.md`):

- Treat permissions as the source of truth; roles are just collections.
- Use least privilege by default: new roles start empty.
- Avoid wildcard permissions unless you are explicitly creating superuser roles.
- Separate domains (`admin`, `user`, `system`) and enforce audience separation.

Production controls:

- Require MFA for admin accounts (outside SwX if not built-in).
- Require strong admin session controls (short-lived tokens; limited IP ranges).
- Make role/permission changes auditable and reviewable.

### Policy engine configuration

ABAC policies are the final authorization layer (`docs/04-core-concepts/POLICY_ENGINE.md`).

Hard requirements:

- Default decision is DENY when no policy matches.
- DENY policies have higher priority than ALLOW policies.
- Policies are owned, versioned, and reviewed (treat as code).

High-value policies to implement early:

- Resource ownership (actor.id == resource.owner_id)
- Team boundary enforcement (actor.team_id == resource.team_id)
- IP allow-list for admin actions (context.ip in approved CIDRs)
- Time-based access for sensitive admin actions

Example IP allow-list policy (conceptual):

```json
{
  "policy_id": "admin.access.whitelisted_ip",
  "name": "Admin Access IP Allow-List",
  "description": "Deny admin actions unless request originates from approved ranges",
  "effect": "allow",
  "action_pattern": "admin:*",
  "resource_type": "*",
  "conditions": [
    {"attribute": "context.ip", "operator": "in", "value": ["203.0.113.0/24", "198.51.100.10/32"]}
  ],
  "priority": 100
}
```

### Permission granularity

Common mistakes:

- Over-broad permissions like `"user:manage"` used everywhere.
- Mixing read/write/delete under one permission.
- Missing resource scoping (team boundary not enforced).

Rules:

- Prefer `resource:read`, `resource:write`, `resource:delete` and add `resource:manage` only for tightly-controlled admin roles.
- Enforce team scoping at the authorization layer, not only in SQL filters.
- Keep a minimal set of admin-only permissions; do not reuse user-domain permissions for admin.

### Team-based access control

Multi-tenant hardening requirements:

- Every tenant-scoped resource must carry `team_id` (or equivalent) and enforce it on all reads/writes.
- Membership checks happen before expensive operations.
- Avoid “global” roles unless truly required.

Audit requirements:

- Log membership changes (`team.member.add`, `team.member.remove`).
- Alert on privileged role grants.

---

## Network Security

### HTTPS enforcement

Hard requirements:

- Terminate TLS at a reverse proxy or load balancer.
- Redirect HTTP to HTTPS.
- Enable HSTS (after confirming all traffic is HTTPS).

Nginx example:

```nginx
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://swx_api:8001;
    }
}
```

### CORS configuration

Do not use `*` origins for authenticated endpoints.

Use explicit origins via `BACKEND_CORS_ORIGINS`:

```bash
BACKEND_CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

Rules:

- Set `allow_credentials` only when you use cookies and your origins are explicit.
- Only allow necessary methods and headers.
- Treat CORS as a browser control; it does not protect non-browser clients.

### Rate limiting

- Keep API-wide rate limits enabled.
- Add stricter limits for:
  - Auth endpoints (see Authentication Hardening)
  - High-cost endpoints (export, search)
  - Admin endpoints

Layering:

- Edge: WAF/CDN (per-IP)
- App: Redis-backed limits (per-user/per-team)
- DB: connection pooling and query timeouts

### IP whitelisting

Use IP allow-lists only for admin and internal-only surfaces.

Implementation options:

- At the edge/load balancer (preferred)
- At the reverse proxy (Nginx/Envoy)
- In-policy engine (`context.ip` conditions) for app-level enforcement

Example (Nginx):

```nginx
location /api/admin/ {
    allow 203.0.113.0/24;
    allow 198.51.100.10/32;
    deny all;
    proxy_pass http://swx_api:8001;
}
```

### DDoS protection

- Use a DDoS-aware edge (cloud WAF/CDN) and enable bot protection.
- Protect expensive endpoints first (search/export/report generation).
- Use request body size limits and timeouts at the proxy.

---

## Database Security

### Connection encryption

Hard requirements:

- Require TLS between app and database.
- Put the database on a private network; no public IP.

Postgres example (URL parameter):

```bash
# SQLAlchemy async URL example
DATABASE_URL="postgresql+asyncpg://swx_user:<password>@db.example.internal:5432/swx_db?ssl=require"
```

If you use managed Postgres:

- Require TLS on the server.
- Use an allow-list of app subnets/security groups.

### Credential rotation

- Use per-environment database users.
- Prefer short-lived credentials where supported (Vault DB secrets engine, IAM auth, etc.).
- Rotate on schedule and on incident.

Rotation checklist:

- Create a new DB user/password.
- Deploy new credentials.
- Verify connections.
- Revoke the old credentials.

Least privilege:

- Use a dedicated application user with the minimum required privileges.
- Use a separate migration user for schema changes; do not run migrations as the app user.
- Restrict outbound connections from the DB (no direct Internet egress).

### Query parameterization

Hard requirements:

- Use ORM/query builders; do not string-concatenate SQL.
- For raw SQL, always bind parameters.

Example (SQLAlchemy bind params):

```python
from sqlalchemy import text

stmt = text("SELECT * FROM users WHERE email = :email")
result = await session.execute(stmt, {"email": email})
```

### Audit logging

Application audit logs:

- Use SwX audit logging for auth/authorization/business events (`docs/04-core-concepts/AUDIT_LOGS.md`).

Database audit logs:

- Enable DB-side audit features (e.g., `pgaudit` on Postgres) for privileged operations.
- Send DB logs to a separate sink from application logs.

---

## Redis Security

Redis is a security dependency when used for token revocation and rate limiting. If Redis is exposed, an attacker can potentially bypass controls or cause a denial of service.

### AUTH configuration

Hard requirements:

- Require authentication (`requirepass` or ACLs).
- Disable dangerous commands for application users where possible.
- Do not expose Redis to the public Internet.

Redis config example:

```conf
bind 127.0.0.1 ::1
protected-mode yes

requirepass <strong-random-password>

# Disable high-risk commands (evaluate based on your use)
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG ""
rename-command DEBUG ""
```

### TLS encryption

Hard requirements:

- Use TLS when Redis traffic crosses hosts or networks you do not fully trust.
- Pin certificates when possible.

If you cannot run Redis with TLS:

- Keep Redis on the same host or private subnet.
- Restrict network paths (security groups, firewall rules).

### Network isolation

- Place Redis in a private subnet.
- Restrict inbound to only API workers.
- If using Kubernetes: use NetworkPolicies to restrict Redis access to the SwX namespace/workloads.

---

## Logging & Monitoring

### Security event logging

Minimum events to log (structured, consistent action names):

- Authentication: `auth.login` (success/failure), `auth.token.refresh`, `auth.password.reset`
- Authorization: `permission.denied`, `policy.denied`
- Abuse: `rate_limit.exceeded`, repeated 401/403 bursts
- Admin changes: role/permission/policy changes, settings changes

Rules:

- Never log secrets, tokens, Authorization headers, or cookies.
- Ensure logs include request correlation (request id) and origin context (IP, user agent) where safe.

### Audit trail requirements

- Audit logs must be append-only and access-controlled.
- Admin access to audit logs must itself be audited.
- Retain logs per your compliance requirements (see Compliance).

### Intrusion detection

Signals to alert on:

- Unusual bursts of failed logins (credential stuffing).
- Tokens used from new geographies/ASNs within short time windows.
- Repeated audience mismatches or revoked token usage.
- Repeated policy denials for sensitive actions.
- Redis connectivity errors coinciding with auth/rate-limit changes (attempted fail-open).

Controls:

- Centralized log aggregation (ELK/OpenSearch/Splunk/etc.).
- Host/container IDS where available.
- Alerts with paging for authentication/authorization control failures.

### Anomaly detection

Minimum detection rules:

- Per-account failed login threshold over time windows.
- Per-IP auth attempts threshold.
- High rate of 403s or policy denials for a single actor.
- Sudden spikes in token refresh usage.

---

## Compliance

### GDPR considerations

Hard requirements:

- Data minimization: collect only what you need.
- Lawful basis: document why you collect/store each category of personal data.
- Access and deletion: implement processes for DSAR (export) and deletion.
- Breach notification: plan to notify within required timelines.

Operational requirements:

- Keep personal data out of logs.
- Ensure backups respect deletion requirements (document your approach).

### SOC 2 requirements

Focus areas (security + availability):

- Access control: least privilege, offboarding, MFA for admin.
- Change management: reviewed and tracked production changes.
- Monitoring: alerts for security control failures.
- Incident response: documented and exercised.
- Vendor management: track third-party systems that can access production data.

### Data retention policies

Define, document, and enforce:

- Audit log retention (example: 365+ days; adjust per requirement).
- Authentication event retention.
- Security alert retention.
- Backup retention and encryption.

Rule:

- Never delete audit logs without an explicit archival process and documented approvals.

---

## Incident Response

### Security incident checklist

Immediate actions (first hour):

1. Identify scope: affected users, teams, endpoints, time window.
2. Contain: block suspicious IPs, disable compromised accounts, reduce attack surface.
3. Preserve evidence: snapshot logs, audit trails, and relevant system metrics.
4. Stop the bleeding: rotate credentials that may be compromised.
5. Communicate internally: define an incident commander and a single channel.

### Token rotation procedure

Threats:

- `SECRET_KEY` compromise allows token forgery.
- Refresh token store/DB compromise allows session extension.

Procedure (key compromise):

1. Rotate `SECRET_KEY`, `REFRESH_SECRET_KEY`, `PASSWORD_RESET_SECRET_KEY` in your secrets system.
2. Deploy and restart all API workers.
3. Revoke tokens:
   - Revoke all user tokens using the blacklist (user-level revoke) where possible.
   - Invalidate refresh tokens in the database if you store them there.
4. Force re-authentication for impacted accounts.
5. Monitor for continued use of old tokens and for new forged tokens.

Minimal commands (generate new secrets):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Breach notification

Requirements vary by jurisdiction and contract. Prepare templates and escalation paths in advance.

Minimum operational plan:

- Determine if personal data was accessed/exfiltrated.
- Notify affected customers/users per legal timelines.
- Provide concrete remediation steps (password reset, session invalidation).
- Publish indicators of compromise if appropriate.

---

**Status:** Production hardening guidance documented.
