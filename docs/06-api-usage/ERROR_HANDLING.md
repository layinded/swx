# Error Handling

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [HTTP Status Codes](#http-status-codes)
3. [Error Response Format](#error-response-format)
4. [Common Errors](#common-errors)
5. [Error Handling Patterns](#error-handling-patterns)
6. [Client-Side Handling](#client-side-handling)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API uses **standard HTTP status codes** and **consistent error response formats** to communicate errors clearly. All errors follow a predictable structure for easy handling.

### Error Response Structure

**Standard Error:**
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "detail": "Additional error details (optional)"
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

## HTTP Status Codes

### Success Codes

**200 OK**
- Request successful
- Response body contains requested data

**201 Created**
- Resource created successfully
- Response body contains created resource
- `Location` header contains resource URL

**204 No Content**
- Request successful, no content to return
- Response body is empty

### Client Error Codes

**400 Bad Request**
- Invalid request format
- Missing required parameters
- Invalid parameter values

**401 Unauthorized**
- Authentication required
- Invalid or expired token
- Missing authentication

**403 Forbidden**
- Permission denied
- Insufficient permissions
- Policy denied

**404 Not Found**
- Resource not found
- Endpoint not found
- Invalid resource ID

**409 Conflict**
- Resource conflict
- Duplicate resource
- Concurrent modification

**422 Unprocessable Entity**
- Validation error
- Invalid data format
- Business rule violation

**429 Too Many Requests**
- Rate limit exceeded
- Too many requests
- Retry after specified time

### Server Error Codes

**500 Internal Server Error**
- Server error
- Unexpected error
- Application error

**502 Bad Gateway**
- Gateway error
- Upstream service error

**503 Service Unavailable**
- Service unavailable
- Maintenance mode
- Temporary unavailability

---

## Error Response Format

### Standard Error

**Format:**
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "detail": "Additional error details (optional)"
}
```

**Example:**
```json
{
  "error": "user_not_found",
  "message": "User not found",
  "detail": "User with ID 123e4567-e89b-12d3-a456-426614174000 not found"
}
```

### Validation Error

**Format:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "field_name",
      "message": "Error message for this field"
    }
  ]
}
```

**Example:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "email",
      "message": "Invalid email format"
    },
    {
      "field": "password",
      "message": "Password must be at least 8 characters"
    }
  ]
}
```

### Rate Limit Error

**Format:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded",
  "limit": 10000,
  "remaining": 0,
  "reset_at": "2026-01-26T12:00:00Z",
  "retry_after": 60
}
```

**Headers:**
```
X-RateLimit-Limit: 10000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706284800
Retry-After: 60
```

---

## Common Errors

### Authentication Errors

**401 Unauthorized - Invalid Token:**
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

**401 Unauthorized - Missing Token:**
```json
{
  "error": "unauthorized",
  "message": "Authentication required"
}
```

**401 Unauthorized - Wrong Audience:**
```json
{
  "error": "unauthorized",
  "message": "Token audience mismatch"
}
```

### Authorization Errors

**403 Forbidden - Permission Denied:**
```json
{
  "error": "forbidden",
  "message": "Permission denied",
  "detail": "User does not have required permission: user:delete"
}
```

**403 Forbidden - Policy Denied:**
```json
{
  "error": "forbidden",
  "message": "Policy denied",
  "detail": "Policy 'team.update.owner' denied: User is not team owner"
}
```

### Validation Errors

**422 Unprocessable Entity - Invalid Email:**
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

**422 Unprocessable Entity - Missing Required Field:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "detail": [
    {
      "field": "password",
      "message": "Field required"
    }
  ]
}
```

### Resource Errors

**404 Not Found - User Not Found:**
```json
{
  "error": "user_not_found",
  "message": "User not found",
  "detail": "User with ID 123e4567-e89b-12d3-a456-426614174000 not found"
}
```

**409 Conflict - Duplicate Email:**
```json
{
  "error": "user_already_exists",
  "message": "User already exists",
  "detail": "User with email user@example.com already exists"
}
```

### Rate Limit Errors

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

---

## Error Handling Patterns

### Retry Logic

**Exponential Backoff:**
```python
import time
import requests

def make_request_with_retry(url, token, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limit - retry with backoff
                retry_after = int(e.response.headers.get("Retry-After", 60))
                wait_time = retry_after * (2 ** attempt)
                time.sleep(wait_time)
                continue
            elif e.response.status_code == 500:
                # Server error - retry with backoff
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Don't retry other errors
                raise
    raise Exception("Max retries exceeded")
```

### Error Classification

**Client Errors (4xx):**
- Don't retry (except 429)
- Fix request and retry
- User action required

**Server Errors (5xx):**
- Retry with backoff
- Temporary errors
- May succeed on retry

**Rate Limit Errors (429):**
- Retry after `Retry-After` seconds
- Respect rate limits
- Implement exponential backoff

---

## Client-Side Handling

### JavaScript/TypeScript

**Basic Error Handling:**
```typescript
async function makeRequest(url: string, token: string) {
  try {
    const response = await fetch(url, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }
    
    return await response.json();
  } catch (error) {
    console.error("Request failed:", error);
    throw error;
  }
}
```

**Error Classification:**
```typescript
async function handleError(response: Response) {
  const error = await response.json();
  
  switch (response.status) {
    case 401:
      // Authentication error - redirect to login
      window.location.href = "/login";
      break;
    case 403:
      // Permission error - show message
      alert("Permission denied");
      break;
    case 404:
      // Not found - show message
      alert("Resource not found");
      break;
    case 429:
      // Rate limit - retry after delay
      const retryAfter = response.headers.get("Retry-After");
      setTimeout(() => makeRequest(url, token), parseInt(retryAfter) * 1000);
      break;
    case 422:
      // Validation error - show field errors
      error.detail.forEach((fieldError: any) => {
        console.error(`${fieldError.field}: ${fieldError.message}`);
      });
      break;
    default:
      // Generic error
      alert(error.message);
  }
}
```

### Python

**Basic Error Handling:**
```python
import requests

def make_request(url, token):
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        error = e.response.json()
        handle_error(e.response.status_code, error)
        raise
```

**Error Classification:**
```python
def handle_error(status_code, error):
    if status_code == 401:
        # Authentication error - refresh token
        refresh_token()
    elif status_code == 403:
        # Permission error - show message
        print(f"Permission denied: {error['message']}")
    elif status_code == 404:
        # Not found - show message
        print(f"Resource not found: {error['message']}")
    elif status_code == 429:
        # Rate limit - retry after delay
        retry_after = int(error.get("retry_after", 60))
        time.sleep(retry_after)
    elif status_code == 422:
        # Validation error - show field errors
        for field_error in error.get("detail", []):
            print(f"{field_error['field']}: {field_error['message']}")
    else:
        # Generic error
        print(f"Error: {error['message']}")
```

---

## Best Practices

### ✅ DO

1. **Handle all error codes**
   ```python
   # ✅ Good - Handle all errors
   if response.status_code == 401:
       # Handle authentication
   elif response.status_code == 403:
       # Handle permission
   elif response.status_code == 429:
       # Handle rate limit
   ```

2. **Retry on transient errors**
   ```python
   # ✅ Good - Retry on 5xx errors
   if response.status_code >= 500:
       retry_with_backoff()
   ```

3. **Respect rate limits**
   ```python
   # ✅ Good - Respect Retry-After
   if response.status_code == 429:
       retry_after = int(response.headers.get("Retry-After", 60))
       time.sleep(retry_after)
   ```

4. **Show user-friendly messages**
   ```python
   # ✅ Good - User-friendly message
   error_message = error.get("message", "An error occurred")
   show_message_to_user(error_message)
   ```

5. **Log errors for debugging**
   ```python
   # ✅ Good - Log errors
   logger.error(f"API error: {error}", extra={"status_code": status_code})
   ```

### ❌ DON'T

1. **Don't ignore errors**
   ```python
   # ❌ Bad - Errors ignored
   try:
       response = requests.get(url)
   except:
       pass  # DON'T DO THIS
   ```

2. **Don't retry on client errors**
   ```python
   # ❌ Bad - Retry on 4xx errors
   if response.status_code == 400:
       retry()  # DON'T DO THIS
   
   # ✅ Good - Don't retry on 4xx
   if response.status_code >= 400 and response.status_code < 500:
       # Don't retry - fix request
   ```

3. **Don't expose technical details to users**
   ```python
   # ❌ Bad - Technical details
   show_message(f"SQL Error: {error['detail']}")
   
   # ✅ Good - User-friendly message
   show_message("An error occurred. Please try again.")
   ```

---

## Next Steps

- Read [API Usage Guide](./API_USAGE.md) for general API usage
- Read [API Reference](./API_REFERENCE.md) for endpoint details
- Read [Pagination & Filtering](./PAGINATION_FILTERING.md) for pagination details

---

**Status:** Error handling documented, ready for implementation.
