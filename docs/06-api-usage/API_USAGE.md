# API Usage Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [Request Format](#request-format)
5. [Response Format](#response-format)
6. [Common Patterns](#common-patterns)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API provides a **RESTful API** with clear endpoints, consistent response formats, and comprehensive error handling. This guide covers how to use the API effectively.

### Key Features

- ✅ **RESTful Design** - Standard HTTP methods and status codes
- ✅ **JSON Format** - All requests and responses in JSON
- ✅ **Token Authentication** - JWT-based authentication
- ✅ **Domain Separation** - Admin and User domains
- ✅ **Pagination** - Built-in pagination support
- ✅ **Filtering** - Query parameter filtering
- ✅ **OpenAPI Docs** - Interactive API documentation

---

## Base URL

### Development

```
http://localhost:8001/api
```

### Production

```
https://api.yourdomain.com/api
```

### API Versioning

**Current Version:** `v1` (default)

**Version in URL:**
```
https://api.yourdomain.com/api/v1
```

**Version in Header:**
```
X-API-Version: v1
```

---

## Authentication

### Token Types

**Access Token:**
- Short-lived (default: 7 days)
- Used for API requests
- Included in `Authorization` header

**Refresh Token:**
- Long-lived (default: 30 days)
- Used to obtain new access tokens
- Stored securely (not in header)

### Authentication Flow

**1. Login:**
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

**2. Use Access Token:**
```bash
GET /api/user/profile/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**3. Refresh Token:**
```bash
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Admin Authentication

**Admin Login:**
```bash
POST /api/admin/auth/
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=password
```

**Admin Token Usage:**
```bash
GET /api/admin/user/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Note:** Admin tokens cannot access user endpoints and vice versa.

---

## Request Format

### HTTP Methods

**GET** - Retrieve resources
```bash
GET /api/user/profile/
```

**POST** - Create resources
```bash
POST /api/auth/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

**PATCH** - Update resources (partial)
```bash
PATCH /api/user/profile/
Content-Type: application/json

{
  "name": "New Name"
}
```

**PUT** - Update resources (full)
```bash
PUT /api/user/profile/
Content-Type: application/json

{
  "name": "New Name",
  "email": "new@example.com"
}
```

**DELETE** - Delete resources
```bash
DELETE /api/user/profile/
```

### Headers

**Required Headers:**
```bash
Content-Type: application/json
Authorization: Bearer <token>
```

**Optional Headers:**
```bash
X-API-Version: v1
X-Request-ID: <request-id>
Accept: application/json
```

### Query Parameters

**Pagination:**
```bash
GET /api/admin/user/?skip=0&limit=100
```

**Filtering:**
```bash
GET /api/admin/user/?email=user@example.com
```

**Sorting:**
```bash
GET /api/admin/user/?order_by=created_at&order=desc
```

---

## Response Format

### Success Response

**Single Resource:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true,
  "created_at": "2026-01-26T12:00:00Z"
}
```

**List of Resources:**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user1@example.com",
    "name": "User 1"
  },
  {
    "id": "223e4567-e89b-12d3-a456-426614174000",
    "email": "user2@example.com",
    "name": "User 2"
  }
]
```

**Paginated Response:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com"
    }
  ],
  "count": 100,
  "skip": 0,
  "limit": 10
}
```

**Message Response:**
```json
{
  "message": "Operation completed successfully"
}
```

### Error Response

**Standard Error:**
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "detail": "Additional error details"
}
```

**Validation Error:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

---

## Common Patterns

### Creating Resources

**User Registration:**
```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password",
  "name": "John Doe"
}
```

**Admin User Creation:**
```bash
POST /api/admin/user/
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password",
  "name": "John Doe",
  "is_active": true
}
```

### Reading Resources

**Get Current User:**
```bash
GET /api/user/profile/
Authorization: Bearer <token>
```

**Get User by ID:**
```bash
GET /api/user/profile/{user_id}
Authorization: Bearer <token>
```

**List All Users (Admin):**
```bash
GET /api/admin/user/
Authorization: Bearer <admin-token>
```

### Updating Resources

**Update Current User:**
```bash
PATCH /api/user/profile/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "New Name"
}
```

**Update User (Admin):**
```bash
PATCH /api/admin/user/{user_id}
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "name": "New Name",
  "is_active": false
}
```

### Deleting Resources

**Delete Current User:**
```bash
DELETE /api/user/profile/
Authorization: Bearer <token>
```

**Delete User (Admin):**
```bash
DELETE /api/admin/user/{user_id}
Authorization: Bearer <admin-token>
```

---

## Error Handling

### HTTP Status Codes

**Success:**
- `200 OK` - Request successful
- `201 Created` - Resource created
- `204 No Content` - Request successful, no content

**Client Errors:**
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded

**Server Errors:**
- `500 Internal Server Error` - Server error
- `502 Bad Gateway` - Gateway error
- `503 Service Unavailable` - Service unavailable

### Error Response Format

**Standard Error:**
```json
{
  "error": "error_code",
  "message": "Human-readable error message"
}
```

**Detailed Error:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

### Common Errors

**Authentication Errors:**
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

**Permission Errors:**
```json
{
  "error": "forbidden",
  "message": "Permission denied"
}
```

**Validation Errors:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

**Rate Limit Errors:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Rate Limiting

### Rate Limit Headers

**Response Headers:**
```
X-RateLimit-Limit: 10000
X-RateLimit-Remaining: 9999
X-RateLimit-Reset: 1706284800
Retry-After: 60
```

### Rate Limit Response

**429 Too Many Requests:**
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

### Handling Rate Limits

**Retry Logic:**
```python
import time
import requests

def make_request_with_retry(url, token, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                continue
            else:
                raise Exception("Rate limit exceeded")
        
        return response.json()
```

---

## Best Practices

### ✅ DO

1. **Use HTTPS in production**
   ```bash
   # ✅ Good - HTTPS
   https://api.yourdomain.com/api
   ```

2. **Store tokens securely**
   ```python
   # ✅ Good - Secure storage
   # Use httpOnly cookies or secure storage
   ```

3. **Handle errors gracefully**
   ```python
   # ✅ Good - Error handling
   try:
       response = requests.get(url)
       response.raise_for_status()
   except requests.HTTPError as e:
       if e.response.status_code == 429:
           # Handle rate limit
       elif e.response.status_code == 401:
           # Handle authentication
   ```

4. **Use pagination for large lists**
   ```bash
   # ✅ Good - Pagination
   GET /api/admin/user/?skip=0&limit=100
   ```

5. **Include request IDs for tracing**
   ```bash
   # ✅ Good - Request ID
   X-Request-ID: <unique-request-id>
   ```

### ❌ DON'T

1. **Don't store tokens in localStorage**
   ```javascript
   // ❌ Bad - localStorage vulnerable to XSS
   localStorage.setItem("token", token);
   
   // ✅ Good - httpOnly cookies or secure storage
   ```

2. **Don't ignore rate limits**
   ```python
   # ❌ Bad - No rate limit handling
   response = requests.get(url)
   
   # ✅ Good - Handle rate limits
   if response.status_code == 429:
       time.sleep(response.headers.get("Retry-After", 60))
   ```

3. **Don't make unnecessary requests**
   ```python
   # ❌ Bad - Multiple requests
   for user_id in user_ids:
       user = requests.get(f"/api/user/{user_id}")
   
   # ✅ Good - Batch request
   users = requests.get("/api/user/bulk", params={"ids": user_ids})
   ```

4. **Don't expose tokens in logs**
   ```python
   # ❌ Bad - Token in logs
   logger.info(f"Token: {token}")
   
   # ✅ Good - No token in logs
   logger.info("Request authenticated")
   ```

---

## Next Steps

- Read [API Reference](./API_REFERENCE.md) for detailed endpoint documentation
- Read [Error Handling](./ERROR_HANDLING.md) for error handling details
- Read [Pagination & Filtering](./PAGINATION_FILTERING.md) for pagination details

---

**Status:** API usage guide documented, ready for implementation.
