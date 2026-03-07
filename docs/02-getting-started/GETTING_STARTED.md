# Getting Started with SwX-API

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [Verifying Installation](#verifying-installation)
7. [Next Steps](#next-steps)

---

## Prerequisites

### Required

- **Python 3.10+** - Check with `python --version`
- **PostgreSQL 12+** - Database server
- **Redis 6+** - Caching and rate limiting
- **Git** - Version control

### Optional

- **Docker & Docker Compose** - Containerized setup
- **Caddy** - Reverse proxy (production)

### System Requirements

- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 10GB free space
- **OS:** Linux, macOS, or Windows (WSL2 recommended)

---

## Installation

### Option 1: Docker (Recommended)

**Fastest way to get started:**

```bash
# Clone repository
git clone <repository-url>
cd swx-api-latest-backend

# Copy environment file
cp .env.example .env

# Start services
docker-compose up --build

# Application will be available at:
# - API: http://localhost:8001/api
# - Docs: http://localhost:8001/docs
```

**Docker services:**
- `swx-api` - FastAPI application
- `postgres` - PostgreSQL database
- `redis` - Redis cache

### Option 2: Local Development

**For development without Docker:**

```bash
# Clone repository
git clone <repository-url>
cd swx-api-latest-backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

### Required Variables

**Database:**
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/swx_db
```

**Secrets:**
```env
SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
REFRESH_SECRET_KEY=your-refresh-secret-key
PASSWORD_RESET_SECRET_KEY=your-password-reset-secret-key
```

**Application:**
```env
PROJECT_NAME=SwX-API
ENVIRONMENT=local
ROUTE_PREFIX=/api
```

### Optional Variables

**Redis:**
```env
REDIS_URL=redis://localhost:6379/0
```

**Email (for notifications):**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAILS_FROM_EMAIL=noreply@example.com
EMAILS_FROM_NAME=SwX API
```

**OAuth (for social login):**
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
FACEBOOK_CLIENT_ID=your-facebook-client-id
FACEBOOK_CLIENT_SECRET=your-facebook-client-secret
```

**Stripe (for billing):**
```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

**Sentry (for error tracking):**
```env
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### Generate Secrets

**Generate secure secrets:**
```bash
# SECRET_KEY
openssl rand -hex 32

# REFRESH_SECRET_KEY
openssl rand -hex 32

# PASSWORD_RESET_SECRET_KEY
openssl rand -hex 32
```

---

## Database Setup

### With Docker

**Automatic setup:**
- Database created automatically
- Migrations run on startup
- Admin user created (if `FIRST_SUPERUSER` set)

### Without Docker

**Manual setup:**

```bash
# Create database
createdb swx_db

# Or using PostgreSQL client
psql -U postgres
CREATE DATABASE swx_db;
\q

# Run migrations
alembic upgrade head

# Create admin user
python scripts/reset_admin_password.py
# Or set in .env:
# FIRST_SUPERUSER=admin@example.com
# FIRST_SUPERUSER_PASSWORD=securepassword
```

### Database Migrations

**Run migrations:**
```bash
# Upgrade to latest
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback
alembic downgrade -1
```

---

## Running the Application

### With Docker

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f swx-api

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Without Docker

**Development server:**
```bash
# Activate virtual environment
source .venv/bin/activate

# Run development server
uvicorn swx_core.main:app --reload --host 0.0.0.0 --port 8001

# Or using Python
python -m uvicorn swx_core.main:app --reload
```

**Production server:**
```bash
# Using gunicorn
gunicorn swx_core.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

---

## Verifying Installation

### 1. Check API Health

```bash
curl http://localhost:8001/api/utils/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### 2. Check API Documentation

Open in browser:
```
http://localhost:8001/docs
```

**Swagger UI** should display all available endpoints.

### 3. Test Admin Login

```bash
curl -X POST http://localhost:8001/api/admin/auth/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=securepassword"
```

**Expected response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### 4. Run System Seed

**Seed initial data:**
```bash
# With Docker
docker-compose exec swx-api python scripts/seed_system.py

# Without Docker
API_URL=http://localhost:8001/api \
  ADMIN_EMAIL=admin@example.com \
  ADMIN_PASSWORD=securepassword \
  python scripts/seed_system.py
```

**This seeds:**
- Permissions
- Roles
- Billing plans and features
- Runtime settings

### 5. Run Full Simulation

**Test all endpoints:**
```bash
# With Docker
docker-compose exec swx-api python scripts/full_user_simulation.py

# Without Docker
API_URL=http://localhost:8001/api \
  ADMIN_EMAIL=admin@example.com \
  ADMIN_PASSWORD=securepassword \
  python scripts/full_user_simulation.py
```

---

## Next Steps

### 1. Read Documentation

- **[Overview](../01-overview/OVERVIEW.md)** - What is SwX-API?
- **[Architecture](../03-architecture/ARCHITECTURE.md)** - System design
- **[Authentication](../04-core-concepts/AUTHENTICATION.md)** - Auth flows

### 2. Explore the API

- Open **Swagger UI**: http://localhost:8001/docs
- Try endpoints with authentication
- Review OpenAPI schema

### 3. Create Your First Feature

**Add a new route:**
```python
# swx_app/routes/v1/my_feature_route.py
from fastapi import APIRouter
from swx_core.auth.user.dependencies import UserDep

router = APIRouter()

@router.get("/my-feature")
async def my_feature(user: UserDep):
    return {"message": "Hello from my feature", "user": user.email}
```

**Add a new model:**
```python
# swx_app/models/my_model.py
from sqlmodel import SQLModel, Field

class MyModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    name: str
    # ... other fields
```

### 4. Run Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_auth.py

# Run with coverage
pytest --cov=swx_core --cov=swx_app
```

### 5. Deploy to Production

- Read **[Operations Guide](../08-operations/OPERATIONS.md)**
- Review **[Production Checklist](../08-operations/PRODUCTION_CHECKLIST.md)**
- Configure reverse proxy (Caddy)
- Set up monitoring

---

## Troubleshooting

### Common Issues

**1. Database connection error**
```bash
# Check PostgreSQL is running
pg_isready

# Check DATABASE_URL in .env
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL
```

**2. Redis connection error**
```bash
# Check Redis is running
redis-cli ping

# Check REDIS_URL in .env
echo $REDIS_URL
```

**3. Migration errors**
```bash
# Check current migration
alembic current

# Reset database (⚠️ DESTRUCTIVE)
alembic downgrade base
alembic upgrade head
```

**4. Port already in use**
```bash
# Find process using port
lsof -i :8001

# Kill process
kill -9 <PID>

# Or change port in .env
PORT=8002
```

**5. Import errors**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Development Workflow

### Daily Development

```bash
# 1. Start services
docker-compose up -d

# 2. Make changes to code
# ... edit files ...

# 3. Test changes
pytest

# 4. Check logs
docker-compose logs -f swx-api

# 5. Stop services
docker-compose down
```

### Adding Features

1. **Create model** in `swx_app/models/`
2. **Create migration** with `alembic revision --autogenerate`
3. **Create repository** in `swx_app/repositories/`
4. **Create service** in `swx_app/services/`
5. **Create controller** in `swx_app/controllers/`
6. **Create route** in `swx_app/routes/v1/`
7. **Add tests** in `swx_app/tests/`

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type check
mypy swx_core swx_app
```

---

## Support

### Documentation

- **Framework Guide** - Comprehensive usage guide
- **API Reference** - Complete API documentation
- **Architecture Docs** - System design
- **Troubleshooting** - Common issues

### Getting Help

- **GitHub Issues** - Bug reports and feature requests
- **Documentation** - Search docs for answers
- **Code Examples** - Review test files

---

## Conclusion

You now have SwX-API running locally! Next steps:

1. ✅ Read the [Overview](../01-overview/OVERVIEW.md)
2. ✅ Explore the [Architecture](../03-architecture/ARCHITECTURE.md)
3. ✅ Review [Core Concepts](../04-core-concepts/)
4. ✅ Build your first feature
5. ✅ Deploy to production

**Happy coding! 🚀**
