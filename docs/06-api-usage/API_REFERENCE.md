# API Reference

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Interactive Documentation](#interactive-documentation)
3. [Endpoint Categories](#endpoint-categories)
4. [Authentication Endpoints](#authentication-endpoints)
5. [User Endpoints](#user-endpoints)
6. [Admin Endpoints](#admin-endpoints)
7. [Utility Endpoints](#utility-endpoints)
8. [OpenAPI Schema](#openapi-schema)

---

## Overview

This document provides a **comprehensive reference** for all SwX-API endpoints. For interactive documentation and testing, use the OpenAPI/Swagger UI at `/docs`.

### Base URL

**Development:**
```
http://localhost:8001/api
```

**Production:**
```
https://api.yourdomain.com/api
```

### Authentication

All protected endpoints require a Bearer token:
```
Authorization: Bearer <token>
```

---

## Interactive Documentation

### Swagger UI

**Access:**
```
http://localhost:8001/docs
```

**Features:**
- Interactive API testing
- Request/response examples
- Schema documentation
- Try it out functionality

### ReDoc

**Access:**
```
http://localhost:8001/redoc
```

**Features:**
- Clean documentation view
- Search functionality
- Schema reference

### OpenAPI JSON

**Access:**
```
http://localhost:8001/openapi.json
```

**Features:**
- Machine-readable schema
- API client generation
- Integration with tools

---

## Endpoint Categories

### Public Endpoints

- `/api/auth/` - User authentication
- `/api/auth/register` - User registration
- `/api/utils/health-check` - Health check
- `/api/utils/health` - Detailed health check

### User Endpoints

- `/api/user/profile/` - User profile management
- `/api/user/profile/{user_id}` - Get user by ID

### Admin Endpoints

- `/api/admin/auth/` - Admin authentication
- `/api/admin/user/` - User management
- `/api/admin/team/` - Team management
- `/api/admin/role/` - Role management
- `/api/admin/permission/` - Permission management
- `/api/admin/policy/` - Policy management
- `/api/admin/billing/` - Billing management
- `/api/admin/settings/` - Settings management
- `/api/admin/job/` - Job management
- `/api/admin/audit/` - Audit log access

### Utility Endpoints

- `/api/utils/health-check` - Basic health check
- `/api/utils/health` - Detailed health check
- `/api/utils/language/` - Language resources

---

## Authentication Endpoints

### User Authentication

**POST `/api/auth/`**
- Login user
- Returns access and refresh tokens

**Request:**
```bash
POST /api/auth/
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**POST `/api/auth/refresh`**
- Refresh access token
- Requires refresh token

**Request:**
```bash
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**POST `/api/auth/register`**
- Register new user
- Public endpoint

**Request:**
```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true
}
```

**POST `/api/auth/logout`**
- Logout user
- Revokes refresh token

**Request:**
```bash
POST /api/auth/logout
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**POST `/api/auth/recover-password`**
- Request password reset
- Sends reset email

**Request:**
```bash
POST /api/auth/recover-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "Password recovery email sent"
}
```

**POST `/api/auth/reset-password`**
- Reset password
- Requires reset token

**Request:**
```bash
POST /api/auth/reset-password
Content-Type: application/json

{
  "token": "reset-token",
  "new_password": "new-secure-password"
}
```

**Response:**
```json
{
  "message": "Password reset successfully"
}
```

### Admin Authentication

**POST `/api/admin/auth/`**
- Login admin user
- Returns admin access token

**Request:**
```bash
POST /api/admin/auth/
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## User Endpoints

### User Profile

**GET `/api/user/profile/`**
- Get current user profile
- Requires user token

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true,
  "created_at": "2026-01-26T12:00:00Z"
}
```

**PATCH `/api/user/profile/`**
- Update current user profile
- Requires user token

**Request:**
```bash
PATCH /api/user/profile/
Content-Type: application/json

{
  "name": "New Name"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "New Name",
  "is_active": true
}
```

**GET `/api/user/profile/{user_id}`**
- Get user by ID
- Requires user token
- Permission check required

**DELETE `/api/user/profile/`**
- Delete current user account
- Requires user token

**Response:**
```json
{
  "message": "User deleted successfully"
}
```

---

## Admin Endpoints

### User Management

**GET `/api/admin/user/`**
- List all users
- Requires admin token
- Supports pagination and filtering

**Request:**
```bash
GET /api/admin/user/?skip=0&limit=100&is_active=true
```

**Response:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "name": "John Doe",
      "is_active": true
    }
  ],
  "count": 100,
  "skip": 0,
  "limit": 100
}
```

**GET `/api/admin/user/{user_id}`**
- Get user by ID
- Requires admin token

**POST `/api/admin/user/`**
- Create new user
- Requires admin token

**Request:**
```bash
POST /api/admin/user/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password",
  "name": "John Doe",
  "is_active": true
}
```

**PATCH `/api/admin/user/{user_id}`**
- Update user
- Requires admin token

**DELETE `/api/admin/user/{user_id}`**
- Delete user
- Requires admin token

### Team Management

**GET `/api/admin/team/`**
- List all teams
- Requires admin token

**GET `/api/admin/team/{team_id}`**
- Get team by ID
- Requires admin token

**POST `/api/admin/team/`**
- Create new team
- Requires admin token

**PATCH `/api/admin/team/{team_id}`**
- Update team
- Requires admin token

**DELETE `/api/admin/team/{team_id}`**
- Delete team
- Requires admin token

### Role Management

**GET `/api/admin/role/`**
- List all roles
- Requires admin token

**GET `/api/admin/role/{role_id}`**
- Get role by ID
- Requires admin token

**POST `/api/admin/role/`**
- Create new role
- Requires admin token

**PATCH `/api/admin/role/{role_id}`**
- Update role
- Requires admin token

**DELETE `/api/admin/role/{role_id}`**
- Delete role
- Requires admin token

### Permission Management

**GET `/api/admin/permission/`**
- List all permissions
- Requires admin token

**GET `/api/admin/permission/{permission_id}`**
- Get permission by ID
- Requires admin token

**POST `/api/admin/permission/`**
- Create new permission
- Requires admin token

**DELETE `/api/admin/permission/{permission_id}`**
- Delete permission
- Requires admin token

### Policy Management

**GET `/api/admin/policy/`**
- List all policies
- Requires admin token

**GET `/api/admin/policy/{policy_id}`**
- Get policy by ID
- Requires admin token

**POST `/api/admin/policy/`**
- Create new policy
- Requires admin token

**PATCH `/api/admin/policy/{policy_id}`**
- Update policy
- Requires admin token

**DELETE `/api/admin/policy/{policy_id}`**
- Delete policy
- Requires admin token

### Billing Management

**GET `/api/admin/billing/plan/`**
- List all billing plans
- Requires admin token

**GET `/api/admin/billing/feature/`**
- List all billing features
- Requires admin token

### Settings Management

**GET `/api/admin/settings/`**
- List all settings
- Requires admin token

**GET `/api/admin/settings/key/{key}`**
- Get setting by key
- Requires admin token

**POST `/api/admin/settings/`**
- Create new setting
- Requires admin token

**PATCH `/api/admin/settings/key/{key}`**
- Update setting
- Requires admin token

**GET `/api/admin/settings/key/{key}/history`**
- Get setting history
- Requires admin token

### Job Management

**GET `/api/admin/job/`**
- List all jobs
- Requires admin token

**GET `/api/admin/job/{job_id}`**
- Get job by ID
- Requires admin token

**POST `/api/admin/job/`**
- Create new job
- Requires admin token

**POST `/api/admin/job/{job_id}/retry`**
- Retry failed job
- Requires admin token

### Audit Log Access

**GET `/api/admin/audit/`**
- List audit logs
- Requires admin token
- Supports filtering and pagination

**Request:**
```bash
GET /api/admin/audit/?skip=0&limit=100&action=auth.login&outcome=success
```

---

## Utility Endpoints

### Health Checks

**GET `/api/utils/health-check`**
- Basic health check
- Public endpoint
- No authentication required

**Response:**
```json
{
  "status": "healthy",
  "service": "swx-api"
}
```

**GET `/api/utils/health`**
- Detailed health check
- Public endpoint
- Includes database connectivity

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

### Language Resources

**GET `/api/utils/language/`**
- List all language resources
- Public endpoint

**GET `/api/utils/language/{language_code}/{key}`**
- Get translation by language code and key
- Public endpoint

**POST `/api/utils/language/`**
- Create language resource
- Requires admin token

---

## OpenAPI Schema

### Schema Location

**OpenAPI JSON:**
```
http://localhost:8001/openapi.json
```

### Schema Features

- Complete endpoint definitions
- Request/response schemas
- Authentication requirements
- Parameter descriptions
- Example values

### Client Generation

**Generate Python Client:**
```bash
openapi-generator generate \
  -i http://localhost:8001/openapi.json \
  -g python \
  -o ./client
```

**Generate TypeScript Client:**
```bash
openapi-generator generate \
  -i http://localhost:8001/openapi.json \
  -g typescript-axios \
  -o ./client
```

---

## Endpoint Summary

### Authentication (7 endpoints)
- User login, refresh, register, logout
- Password recovery and reset
- Admin login

### User Profile (4 endpoints)
- Get, update, delete current user
- Get user by ID

### Admin User Management (5 endpoints)
- List, get, create, update, delete users

### Admin Team Management (5 endpoints)
- List, get, create, update, delete teams

### Admin Role Management (5 endpoints)
- List, get, create, update, delete roles

### Admin Permission Management (4 endpoints)
- List, get, create, delete permissions

### Admin Policy Management (5 endpoints)
- List, get, create, update, delete policies

### Admin Billing (2 endpoints)
- List plans and features

### Admin Settings (5 endpoints)
- List, get, create, update settings
- Get setting history

### Admin Jobs (4 endpoints)
- List, get, create jobs
- Retry failed jobs

### Admin Audit (1 endpoint)
- List audit logs

### Utilities (3 endpoints)
- Health checks (2)
- Language resources (1)

**Total: ~50 endpoints**

---

## Next Steps

- Use [Swagger UI](http://localhost:8001/docs) for interactive testing
- Read [API Usage Guide](./API_USAGE.md) for usage patterns
- Read [Error Handling](./ERROR_HANDLING.md) for error handling
- Read [Pagination & Filtering](./PAGINATION_FILTERING.md) for pagination

---

**Status:** API reference documented, ready for implementation.
