# Pagination & Filtering

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Pagination](#pagination)
3. [Filtering](#filtering)
4. [Sorting](#sorting)
5. [Search](#search)
6. [Best Practices](#best-practices)

---

## Overview

SwX-API supports **pagination, filtering, and sorting** for efficient data retrieval. All list endpoints support these features via query parameters.

### Key Features

- ✅ **Offset Pagination** - Skip and limit parameters
- ✅ **Query Filtering** - Filter by field values
- ✅ **Sorting** - Order by field, ascending/descending
- ✅ **Search** - Full-text search (where supported)
- ✅ **Consistent Format** - Same pattern across all endpoints

---

## Pagination

### Pagination Parameters

**Skip:**
- Number of records to skip
- Default: `0`
- Example: `skip=10` (skip first 10 records)

**Limit:**
- Maximum number of records to return
- Default: `100`
- Maximum: `1000` (configurable)
- Example: `limit=50` (return 50 records)

### Pagination Usage

**Basic Pagination:**
```bash
GET /api/admin/user/?skip=0&limit=100
```

**Next Page:**
```bash
GET /api/admin/user/?skip=100&limit=100
```

**Third Page:**
```bash
GET /api/admin/user/?skip=200&limit=100
```

### Paginated Response

**Format:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com"
    }
  ],
  "count": 1000,
  "skip": 0,
  "limit": 100
}
```

**Fields:**
- `data` - Array of resources
- `count` - Total number of resources
- `skip` - Number of records skipped
- `limit` - Maximum number of records returned

### Pagination Examples

**First Page:**
```bash
GET /api/admin/user/?skip=0&limit=10
```

**Response:**
```json
{
  "data": [...],
  "count": 100,
  "skip": 0,
  "limit": 10
}
```

**Second Page:**
```bash
GET /api/admin/user/?skip=10&limit=10
```

**Response:**
```json
{
  "data": [...],
  "count": 100,
  "skip": 10,
  "limit": 10
}
```

### Client-Side Pagination

**JavaScript Example:**
```javascript
async function fetchUsers(page = 1, pageSize = 10) {
  const skip = (page - 1) * pageSize;
  const response = await fetch(
    `/api/admin/user/?skip=${skip}&limit=${pageSize}`,
    {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    }
  );
  const data = await response.json();
  return {
    users: data.data,
    total: data.count,
    page: page,
    pageSize: pageSize,
    totalPages: Math.ceil(data.count / pageSize)
  };
}
```

**Python Example:**
```python
def fetch_users(page=1, page_size=10):
    skip = (page - 1) * page_size
    response = requests.get(
        f"/api/admin/user/?skip={skip}&limit={page_size}",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    return {
        "users": data["data"],
        "total": data["count"],
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(data["count"] / page_size)
    }
```

---

## Filtering

### Filter Parameters

**Field Filters:**
- Filter by specific field values
- Format: `field_name=value`
- Example: `email=user@example.com`

**Multiple Filters:**
- Combine multiple filters with `&`
- Example: `email=user@example.com&is_active=true`

### Filtering Examples

**Filter by Email:**
```bash
GET /api/admin/user/?email=user@example.com
```

**Filter by Active Status:**
```bash
GET /api/admin/user/?is_active=true
```

**Multiple Filters:**
```bash
GET /api/admin/user/?is_active=true&email=user@example.com
```

### Filter Operators

**Equality:**
```bash
# Exact match
GET /api/admin/user/?email=user@example.com
```

**Inequality:**
```bash
# Not equal (if supported)
GET /api/admin/user/?is_active=!true
```

**Range:**
```bash
# Date range (if supported)
GET /api/admin/user/?created_at__gte=2026-01-01&created_at__lte=2026-01-31
```

### Filter Response

**Filtered Results:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "is_active": true
    }
  ],
  "count": 1,
  "skip": 0,
  "limit": 100
}
```

---

## Sorting

### Sort Parameters

**Order By:**
- Field to sort by
- Format: `order_by=field_name`
- Example: `order_by=created_at`

**Order Direction:**
- Ascending or descending
- Format: `order=asc` or `order=desc`
- Default: `asc`
- Example: `order=desc`

### Sorting Examples

**Sort by Created Date:**
```bash
GET /api/admin/user/?order_by=created_at&order=desc
```

**Sort by Email:**
```bash
GET /api/admin/user/?order_by=email&order=asc
```

**Multiple Sort Fields:**
```bash
# If supported
GET /api/admin/user/?order_by=created_at,email&order=desc,asc
```

### Sort Response

**Sorted Results:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "created_at": "2026-01-26T12:00:00Z"
    }
  ],
  "count": 100,
  "skip": 0,
  "limit": 100
}
```

---

## Search

### Search Parameters

**Search Query:**
- Full-text search (where supported)
- Format: `search=query`
- Example: `search=john`

**Search Fields:**
- Fields to search in (if supported)
- Format: `search_fields=field1,field2`
- Example: `search_fields=name,email`

### Search Examples

**Basic Search:**
```bash
GET /api/admin/user/?search=john
```

**Search in Specific Fields:**
```bash
GET /api/admin/user/?search=john&search_fields=name,email
```

### Search Response

**Search Results:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "name": "John Doe"
    }
  ],
  "count": 1,
  "skip": 0,
  "limit": 100
}
```

---

## Combined Usage

### Pagination + Filtering

**Example:**
```bash
GET /api/admin/user/?skip=0&limit=10&is_active=true&email=user@example.com
```

### Pagination + Sorting

**Example:**
```bash
GET /api/admin/user/?skip=0&limit=10&order_by=created_at&order=desc
```

### Filtering + Sorting

**Example:**
```bash
GET /api/admin/user/?is_active=true&order_by=created_at&order=desc
```

### All Combined

**Example:**
```bash
GET /api/admin/user/?skip=0&limit=10&is_active=true&order_by=created_at&order=desc&search=john
```

---

## Best Practices

### ✅ DO

1. **Use pagination for large lists**
   ```bash
   # ✅ Good - Pagination
   GET /api/admin/user/?skip=0&limit=100
   ```

2. **Use appropriate page sizes**
   ```bash
   # ✅ Good - Reasonable page size
   GET /api/admin/user/?skip=0&limit=50
   
   # ❌ Bad - Too large
   GET /api/admin/user/?skip=0&limit=10000
   ```

3. **Combine filters for precise results**
   ```bash
   # ✅ Good - Multiple filters
   GET /api/admin/user/?is_active=true&email=user@example.com
   ```

4. **Use sorting for ordered results**
   ```bash
   # ✅ Good - Sort by date
   GET /api/admin/user/?order_by=created_at&order=desc
   ```

5. **Handle pagination on client**
   ```javascript
   // ✅ Good - Client-side pagination
   const page = 1;
   const pageSize = 10;
   const skip = (page - 1) * pageSize;
   ```

### ❌ DON'T

1. **Don't fetch all records**
   ```bash
   # ❌ Bad - No pagination
   GET /api/admin/user/
   
   # ✅ Good - Pagination
   GET /api/admin/user/?skip=0&limit=100
   ```

2. **Don't use very large page sizes**
   ```bash
   # ❌ Bad - Too large
   GET /api/admin/user/?skip=0&limit=10000
   
   # ✅ Good - Reasonable size
   GET /api/admin/user/?skip=0&limit=100
   ```

3. **Don't skip error handling**
   ```python
   # ❌ Bad - No error handling
   response = requests.get(url)
   data = response.json()
   
   # ✅ Good - Error handling
   response = requests.get(url)
   response.raise_for_status()
   data = response.json()
   ```

---

## Next Steps

- Read [API Usage Guide](./API_USAGE.md) for general API usage
- Read [API Reference](./API_REFERENCE.md) for endpoint details
- Read [Error Handling](./ERROR_HANDLING.md) for error handling details

---

**Status:** Pagination & filtering documented, ready for implementation.
