# SwX v2.0.0 Production Deployment Guide

**Version:** 2.0.0  
**Last Updated:** 2026-02-28

---

## Table of Contents

1. [Prerequisites Checklist](#prerequisites-checklist)
2. [Docker Deployment](#docker-deployment)
3. [Multi-Node Deployment](#multi-node-deployment)
4. [Database Setup](#database-setup)
5. [Redis Setup](#redis-setup)
6. [Celery Workers](#celery-workers)
7. [Monitoring & Observability](#monitoring--observability)
8. [Zero-Downtime Deployment](#zero-downtime-deployment)

---

## Prerequisites Checklist

### Infrastructure Requirements

- Compute (single node): minimum 2 vCPU / 4GB RAM; 8GB+ recommended if running DB + API + workers on one host
- Compute (multi node): separate API nodes and worker nodes; DB and Redis managed or dedicated nodes
- Storage: SSD-backed persistent storage for PostgreSQL/TimescaleDB; size for data + WAL + backups
- Network: public inbound 80/443 only (reverse proxy); private-only DB/Redis; outbound HTTPS for third-party integrations
- DNS: A/AAAA for `api.<domain>` and any ops endpoints you expose (Grafana/Flower)
- Time sync: NTP enabled (required for token expiry correctness and log ordering)

### Software Dependencies

- Docker Engine and Docker Compose v2 (if using Compose)
- `curl` available on hosts (smoke checks and debugging)
- PostgreSQL client tools (`psql`, `pg_dump`) on an ops host or via containers
- Optional but common:
  - PgBouncer for database connection pooling
  - nginx or Caddy as reverse proxy / TLS termination
  - Prometheus + Grafana

### Security Requirements

- TLS termination and HTTPS-only external access
- Secret storage (do not commit `.env`; restrict file permissions; prefer a secrets manager)
- Firewall rules:
  - public: allow 80/443 to reverse proxy only
  - private: allow DB (5432) and Redis (6379/26379) only from trusted subnets
- Least-privilege DB roles:
  - runtime role for API/workers
  - migration role with schema-altering permissions
- Logging and auditing:
  - ensure logs do not contain credentials, tokens, or full request bodies
  - define retention and access controls

---

## Docker Deployment

Repository references:

- `Dockerfile` (multi-stage build, venv at `/app/.venv`)
- `docker-compose.production.yml` (production stack)
- `docker-compose.yml` (development stack; includes TimescaleDB image)
- `.env.example` (baseline environment variables)
- `Caddyfile` (reverse proxy)

Note: if you use Caddy in production, review `Caddyfile`. Automatic HTTPS should be enabled for public domains (do not keep `auto_https off` in a production configuration).

### Dockerfile Explanation

`Dockerfile` builds a runtime image as follows:

- Stage 1 (builder): creates a virtualenv and installs dependencies using `uv`/`pip`
- Stage 2 (runtime): copies the venv and code, installs `curl` (used by container healthchecks), exposes `8000`, runs `uvicorn swx_core.main:app`

Operational notes:

- The container listens on `8000` internally; expose it only to the reverse proxy.
- For multi-node, avoid running schema migrations in every web container (see [Migration Deployment](#migration-deployment)).

### Environment Variables

SwX reads configuration from `.env` via `swx_core/config/settings.py`.

Minimum production set:

```dotenv
ENVIRONMENT=production
DOMAIN=example.com

# Secrets (generate strong random values; do not reuse across environments)
SECRET_KEY=...
REFRESH_SECRET_KEY=...
PASSWORD_RESET_SECRET_KEY=...

# Database
DB_HOST=db
DB_PORT=5432
DB_USER=swx_user
DB_PASSWORD=...
DB_NAME=swx_db

# Redis
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=

# Bootstrap admin
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=...

# CORS
BACKEND_CORS_ORIGINS=https://app.example.com
```

Common optional:

```dotenv
LOG_LEVEL=warning
SENTRY_DSN=

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
EMAILS_FROM_EMAIL=noreply@example.com
```

Generating secrets:

```bash
# 32+ random bytes, base64
openssl rand -base64 48
```

### Volume Management

- Database volume must persist across container replacement.
- Redis persistence is optional; if you enable AOF/RDB, persist `/data`.
- Reverse proxy state:
  - Caddy requires persistent volumes for `/data` and `/config`.

### Network Configuration

- Run services on a dedicated private network.
- Do not publish DB/Redis ports publicly.
- Only publish 80/443 on the reverse proxy.

### Health Checks

SwX provides:

- `GET /api/utils/health-check` (basic liveness)
- `GET /api/utils/health` (readiness; includes DB connectivity)

Compose healthcheck example:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/utils/health-check"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 40s
```

### Docker Compose Configuration

The repository includes `docker-compose.production.yml` with `caddy`, `db`, `redis`, and `swx-api`. The following is a complete production Compose example that also includes Celery services and a controlled one-off migration job.

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    environment:
      - DOMAIN=${DOMAIN}
      - CADDY_EMAIL=${CADDY_EMAIL:-${EMAILS_FROM_EMAIL:-admin@example.com}}
    depends_on:
      - swx-api

  db:
    image: postgres:15
    restart: always
    env_file:
      - .env
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - app-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 30s

  redis:
    image: redis:7-alpine
    restart: always
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # One-off job: migrations + seed + bootstrap admin.
  # Run this explicitly during deployment.
  migrate:
    image: swx-api:2.0.0
    build:
      context: .
      dockerfile: Dockerfile
    restart: "no"
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - DB_HOST=db
      - REDIS_HOST=redis
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: ["/bin/bash", "-lc", "python swx_core/database/db_setup.py"]

  swx-api:
    image: swx-api:2.0.0
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - DB_HOST=db
      - REDIS_HOST=redis
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command:
      ["/app/.venv/bin/uvicorn", "swx_core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/utils/health-check"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 40s

  celery-worker:
    image: swx-api:2.0.0
    restart: always
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - DB_HOST=db
      - REDIS_HOST=redis
    depends_on:
      redis:
        condition: service_healthy
      db:
        condition: service_healthy
    command: ["/bin/bash", "-lc", "celery -A workers.celery_app worker --loglevel=info --concurrency=4"]
    healthcheck:
      test: ["CMD", "celery", "-A", "workers.celery_app", "inspect", "ping", "-d", "celery@$$HOSTNAME"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  celery-beat:
    image: swx-api:2.0.0
    restart: always
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - REDIS_HOST=redis
    depends_on:
      redis:
        condition: service_healthy
    command: ["/bin/bash", "-lc", "celery -A workers.celery_app beat --loglevel=info"]
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f 'celery.*beat' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  celery-flower:
    image: swx-api:2.0.0
    restart: always
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - REDIS_HOST=redis
    depends_on:
      redis:
        condition: service_healthy
      celery-worker:
        condition: service_healthy
    command: ["/bin/bash", "-lc", "celery -A workers.celery_app flower --port=5555"]
    ports:
      - "127.0.0.1:5555:5555"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5555/api/workers"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

volumes:
  app-db-data:
  redis-data:
  caddy-data:
  caddy-config:

networks:
  default:
    name: swx-api-network
```

Deployment commands:

```bash
cp .env.example .env
# Edit .env for production.

docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d db redis

# Run migrations + seed once (controlled step)
docker compose -f docker-compose.production.yml run --rm migrate

docker compose -f docker-compose.production.yml up -d swx-api celery-worker celery-beat caddy

curl -fsS https://api.${DOMAIN}/api/utils/health-check

# Scale workers (example)
docker compose -f docker-compose.production.yml up -d --scale celery-worker=3

# Scale API replicas on a single host (only if your reverse proxy/load balancer is configured for it)
docker compose -f docker-compose.production.yml up -d --scale swx-api=2
```

---

## Multi-Node Deployment

### Horizontal Scaling Architecture

Reference layout:

- Load balancer: nginx (public)
- API nodes: `swx-api` containers only (stateless)
- Worker nodes: Celery workers (queue-separated) + one Beat instance
- Data services: PostgreSQL/TimescaleDB + PgBouncer + Redis (HA)

Key principles:

- API nodes must not store local state.
- Run schema migrations as a one-off deploy step, not inside every API container.
- Use PgBouncer to protect PostgreSQL connection limits.

### Load Balancer Configuration (nginx Example)

Example `nginx.conf`:

```nginx
worker_processes auto;
events { worker_connections 1024; }

http {
  upstream swx_api_upstream {
    least_conn;
    server api-1:8000 max_fails=3 fail_timeout=10s;
    server api-2:8000 max_fails=3 fail_timeout=10s;
    server api-3:8000 max_fails=3 fail_timeout=10s;
    keepalive 64;
  }

  server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
  }

  server {
    listen 443 ssl http2;
    server_name api.example.com;

    # ssl_certificate     /etc/nginx/certs/fullchain.pem;
    # ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location / {
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header Connection "";
      proxy_next_upstream error timeout http_502 http_503 http_504;
      proxy_pass http://swx_api_upstream;
    }

    location = /api/utils/health-check {
      access_log off;
      proxy_pass http://swx_api_upstream;
    }
  }
}
```

### Session Handling (Redis)

SwX can be deployed stateless with JWT (preferred). If you introduce server-side session state, store session data in Redis.

Operational requirements:

- TTL for all session keys
- Key prefixing to avoid collisions (`swx:sess:*`)
- Redis HA (Sentinel or managed)

If you rely on Starlette `SessionMiddleware`, ensure cookies are HTTPS-only in production (code change required; current default is `https_only=False`).

### Database Connection Pooling

Use PgBouncer in front of PostgreSQL:

- point SwX runtime to PgBouncer (`DB_HOST=pgbouncer`, `DB_PORT=6432`)
- keep a direct connection path for migrations (optional; depends on migration patterns)

### Celery Worker Scaling

`workers/celery_app.py` routes tasks to queues:

- `billing`, `notifications`, `audit`, `events`, `cleanup`

Scale guidance:

- dedicate workers per queue (`-Q billing`, etc.)
- run exactly one Beat instance
- size concurrency per node (`--concurrency`) based on CPU and task type

---

## Database Setup

### PostgreSQL Configuration

Baseline:

- enable `pg_stat_statements` for query profiling
- set `max_connections` based on PgBouncer capacity + maintenance
- configure WAL/archiving if you need PITR

Example extensions:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### TimescaleDB for Time-Series

If you use TimescaleDB:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

Example hypertable conversion:

```sql
SELECT create_hypertable('audit_log', by_range('created_at'), if_not_exists => TRUE);
```

### Connection Pooling (PgBouncer)

Example `pgbouncer.ini`:

```ini
[databases]
swx_db = host=db port=5432 dbname=swx_db

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
reserve_pool_size = 10
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits
```

### Migration Deployment

SwX includes `python swx_core/database/db_setup.py`, which:

- waits for DB readiness
- runs `alembic upgrade head`
- creates/updates the bootstrap admin user
- seeds initial language data

Recommended production process:

1. Run migrations/seeding as a controlled one-off step (`docker compose run --rm migrate` or CI job)
2. Deploy/roll API and worker nodes

Direct commands:

```bash
alembic upgrade head
python swx_core/database/db_setup.py
```

### Backup Procedures

Logical backup:

```bash
pg_dump -h <host> -U <user> -d <db> -Fc -f swx_db.dump
```

Compose DB container backup:

```bash
docker compose exec -T db pg_dump -U ${DB_USER} -d ${DB_NAME} -Fc > swx_db.dump
```

Production minimum:

- nightly backups + retention
- periodic restore tests
- PITR (managed service or WAL archiving) if RPO/RTO require it

---

## Redis Setup

### Redis Configuration

Example `redis.conf` excerpt:

```text
bind 0.0.0.0
protected-mode yes
appendonly yes
appendfsync everysec
maxmemory 1gb
maxmemory-policy allkeys-lru
tcp-keepalive 300
```

### Sentinel for HA

Use Sentinel (or managed Redis) when Redis is required for Celery broker/backend and rate limiting.

Example `sentinel.conf` excerpt:

```text
sentinel monitor mymaster redis-1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1
```

### Cluster Mode

Use Redis Cluster when you need sharding; it increases client and operational complexity.

### Memory Management

- set `maxmemory`
- choose eviction policy explicitly
- monitor `used_memory`, `evicted_keys`, `connected_clients`

### Persistence Options

- RDB: lower overhead, larger data loss window
- AOF: higher durability, higher write overhead
- Mixed: AOF enabled with periodic RDB

---

## Celery Workers

### Worker Configuration

Celery configuration lives in `workers/celery_app.py`:

- broker/backend: `settings.REDIS_URL`
- retries: exponential backoff and max retries
- routing: queue-based routing for task groups
- beat: scheduled periodic tasks

### Queue Routing

Example queue-specific workers:

```bash
celery -A workers.celery_app worker -Q billing --loglevel=info --concurrency=2
celery -A workers.celery_app worker -Q notifications --loglevel=info --concurrency=4
celery -A workers.celery_app worker -Q audit --loglevel=info --concurrency=2
```

### Beat Scheduler

Run exactly one Beat instance per environment:

```bash
celery -A workers.celery_app beat --loglevel=info
```

### Flower Monitoring

Run Flower and expose it privately; proxy it with authentication if you must expose it.

```bash
celery -A workers.celery_app flower --port=5555
```

### Autoscaling

Celery autoscaling example:

```bash
celery -A workers.celery_app worker --loglevel=info --autoscale=20,4
```

---

## Monitoring & Observability

### Prometheus Metrics Endpoint

SwX includes a Prometheus metrics middleware implementation in `swx_core/middleware/metrics_middleware.py`. Exposing a `/metrics` endpoint requires wiring it into the FastAPI app (application code change).

Example wiring:

```python
from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from swx_core.middleware.metrics_middleware import MetricsMiddleware, MetricsConfig, init_metrics

metrics = init_metrics(MetricsConfig(app_name="swx_api"))
app.add_middleware(MetricsMiddleware, metrics=metrics)

@app.get("/metrics")
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

Prometheus scrape example (`prometheus.yml`):

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: swx-api
    metrics_path: /metrics
    static_configs:
      - targets: ["swx-api:8000"]
```

### Docker Compose Example (Prometheus + Grafana + Loki)

This is a complete Compose example for observability. It assumes you have a working `/metrics` endpoint.

```yaml
services:
  prometheus:
    image: prom/prometheus:v2.52.0
    restart: always
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"

  grafana:
    image: grafana/grafana:10.4.3
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-changeme}
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus

  loki:
    image: grafana/loki:3.0.0
    restart: always
    command: ["-config.file=/etc/loki/local-config.yaml"]
    ports:
      - "127.0.0.1:3100:3100"

  promtail:
    image: grafana/promtail:3.0.0
    restart: always
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/log:/var/log:ro
      - ./promtail.yml:/etc/promtail/config.yml:ro
    command: ["-config.file=/etc/promtail/config.yml"]
    depends_on:
      - loki

volumes:
  prometheus-data:
  grafana-data:
```

### Grafana Dashboards

- API latency, error rate, request throughput
- PostgreSQL (connections, slow queries, locks)
- Redis (memory, evictions, clients)
- Celery (queue depth, task runtime; via Flower or custom metrics)

### Log Aggregation

Supported approaches:

- Loki + Promtail
- ELK/Opensearch
- Cloud-native logging

Minimum requirements:

- centralized logs for API and workers
- retention policy
- alerting on sustained error spikes

### Alerting Rules

Prometheus rule examples:

```yaml
groups:
  - name: swx-api
    rules:
      - alert: SwxApiDown
        expr: up{job="swx-api"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SwX API is down"

      - alert: SwxApiHigh5xxRate
        expr: rate(swx_api_http_requests_total{status_code=~"5.."}[5m]) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High 5xx rate"
```

### Health Endpoints

- `GET /api/utils/health-check` (liveness)
- `GET /api/utils/health` (readiness)

---

## Zero-Downtime Deployment

### Blue-Green Deployment

Pattern:

- run two independent stacks (blue and green)
- run migrations as a controlled step
- switch load balancer upstream to the new stack
- keep the old stack for fast rollback

Compose example (project names):

```bash
docker compose -p swx-blue -f docker-compose.production.yml up -d --build
docker compose -p swx-green -f docker-compose.production.yml up -d --build

# Switch upstream in nginx and reload.
nginx -s reload
```

### Rolling Updates

Rolling updates require an orchestrator that supports health-aware staged replacement. With plain Docker Compose, implement rolling behavior externally:

- add new API nodes
- verify health
- shift traffic
- drain and remove old API nodes

### Database Migrations Without Downtime

Use expand/contract migrations:

1. Additive schema changes first (new nullable columns/tables)
2. Deploy application that supports both old and new schema
3. Backfill data in batches
4. Remove old schema in a later deploy

Operational notes:

- avoid long-running table rewrites
- use non-blocking index creation where supported (`CREATE INDEX CONCURRENTLY` on PostgreSQL)
- keep migrations short and observable

---

## Appendix: nginx + Compose (Example)

If you prefer nginx for reverse proxy and load balancing, this is a complete Compose example for a single host (certificate configuration omitted).

```yaml
services:
  nginx:
    image: nginx:1.25-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      # - ./certs:/etc/nginx/certs:ro
    depends_on:
      - swx-api

  swx-api:
    image: swx-api:2.0.0
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    env_file:
      - .env
    environment:
      - DOCKERIZED=true
      - DB_HOST=pgbouncer
      - DB_PORT=6432
      - REDIS_HOST=redis
    command:
      ["/app/.venv/bin/uvicorn", "swx_core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

  pgbouncer:
    image: edoburu/pgbouncer:1.22.1
    restart: always
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_NAME=${DB_NAME}
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=1000
      - DEFAULT_POOL_SIZE=20
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15
    restart: always
    env_file:
      - .env
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - app-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 30s

  redis:
    image: redis:7-alpine
    restart: always
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data

volumes:
  app-db-data:
  redis-data:
```

---

## Next Steps

- Review `docs/08-operations/PRODUCTION_CHECKLIST.md`
- Review `docs/08-operations/MONITORING.md`
