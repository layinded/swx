# Async Model & Performance

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Async Guarantees](#async-guarantees)
3. [What Is Allowed](#what-is-allowed)
4. [Blocking Pitfalls](#blocking-pitfalls)
5. [Concurrency Model](#concurrency-model)
6. [Performance Tuning](#performance-tuning)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API is **fully async** using FastAPI's async capabilities and asyncio. Understanding the async model is critical for:

- **Performance** - Non-blocking operations enable high concurrency
- **Correctness** - Blocking operations can deadlock or degrade performance
- **Scalability** - Async enables handling many concurrent requests

### Key Principles

1. **All route handlers are async**
2. **All database operations are async**
3. **All service calls are async**
4. **Blocking operations must be offloaded**

---

## Async Guarantees

### FastAPI Async Model

**FastAPI uses asyncio:**
- Each request runs in an async context
- Multiple requests handled concurrently
- Event loop manages all async operations

**Concurrency:**
- Multiple requests processed simultaneously
- No thread pool for request handling
- Single event loop for all requests

### Database Operations

**All database operations are async:**
```python
# ✅ Good - Async database operation
result = await session.execute(stmt)
users = result.scalars().all()

# ❌ Bad - Synchronous database operation
result = session.execute(stmt)  # Blocking!
users = result.scalars().all()
```

**Connection Pooling:**
- SQLAlchemy async connection pool
- Multiple connections per worker
- Connections reused across requests

### Redis Operations

**All Redis operations are async:**
```python
# ✅ Good - Async Redis operation
await redis.set("key", "value")
value = await redis.get("key")

# ❌ Bad - Synchronous Redis operation
redis.set("key", "value")  # Blocking!
value = redis.get("key")
```

---

## What Is Allowed

### ✅ Allowed Operations

**1. Async Database Queries:**
```python
@router.get("/users")
async def list_users(session: SessionDep):
    stmt = select(User)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return users
```

**2. Async Service Calls:**
```python
@router.get("/users/{user_id}")
async def get_user(user_id: UUID, session: SessionDep):
    user = await user_service.get_user_by_id(session, user_id)
    return user
```

**3. Async HTTP Requests:**
```python
import httpx

@router.get("/external-data")
async def get_external_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

**4. Async File I/O (via thread pool):**
```python
import asyncio

@router.post("/upload")
async def upload_file(file: UploadFile):
    content = await file.read()  # Async file read
    # Or use thread pool for blocking I/O
    content = await asyncio.to_thread(open("file.txt").read)
```

**5. Async Sleep:**
```python
import asyncio

@router.get("/delayed")
async def delayed_response():
    await asyncio.sleep(5)  # Non-blocking sleep
    return {"message": "Delayed response"}
```

---

## Blocking Pitfalls

### ❌ NEVER Block the Event Loop

**1. Synchronous Sleep:**
```python
# ❌ BAD - Blocks event loop
import time
time.sleep(5)  # DON'T DO THIS

# ✅ GOOD - Non-blocking
import asyncio
await asyncio.sleep(5)
```

**2. Synchronous File I/O:**
```python
# ❌ BAD - Blocks event loop
with open("file.txt") as f:
    data = f.read()  # DON'T DO THIS

# ✅ GOOD - Use thread pool
data = await asyncio.to_thread(open("file.txt").read)

# ✅ GOOD - Use async file library
import aiofiles
async with aiofiles.open("file.txt") as f:
    data = await f.read()
```

**3. Synchronous Database Operations:**
```python
# ❌ BAD - Blocks event loop
result = session.execute(stmt)  # DON'T DO THIS

# ✅ GOOD - Async
result = await session.execute(stmt)
```

**4. CPU-Intensive Operations:**
```python
# ❌ BAD - Blocks event loop
def heavy_computation():
    result = 0
    for i in range(10000000):
        result += i * i
    return result

# ✅ GOOD - Use thread pool
result = await asyncio.to_thread(heavy_computation)
```

**5. Synchronous HTTP Requests:**
```python
# ❌ BAD - Blocks event loop
import requests
response = requests.get("https://api.example.com")  # DON'T DO THIS

# ✅ GOOD - Async
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("https://api.example.com")
```

---

## Concurrency Model

### Request Handling

**Multiple Requests Concurrently:**
```
Request 1 → Handler → await db.query() → [waiting] → Response
Request 2 → Handler → await db.query() → [waiting] → Response
Request 3 → Handler → await db.query() → [waiting] → Response
```

**Event Loop:**
- Single event loop for all requests
- Switches between requests during `await`
- No thread pool for request handling

### Database Concurrency

**Connection Pool:**
- Multiple connections per worker
- Connections shared across requests
- Automatic connection management

**Example:**
```python
# Worker 1: 10 connections
# Request 1 uses connection 1
# Request 2 uses connection 2
# ...
# Request 10 uses connection 10
# Request 11 waits for available connection
```

### Background Tasks

**Background tasks run in separate async tasks:**
```python
from fastapi import BackgroundTasks

@router.post("/process")
async def process_data(data: dict, background_tasks: BackgroundTasks):
    # Add background task
    background_tasks.add_task(process_async, data)
    return {"status": "processing"}
```

**Job Runner:**
- Separate async task
- Polls for jobs
- Executes jobs concurrently (up to max_concurrent)

---

## Performance Tuning

### Database Optimization

**1. Use Indexes:**
```python
# ✅ Good - Indexed query
stmt = select(User).where(User.email == email)  # email is indexed

# ❌ Bad - Unindexed query
stmt = select(User).where(User.name == name)  # name not indexed
```

**2. Limit Results:**
```python
# ✅ Good - Limited results
stmt = select(User).limit(100)

# ❌ Bad - Unlimited results
stmt = select(User)  # Could return millions
```

**3. Use Eager Loading:**
```python
# ✅ Good - Eager load relationships
from sqlalchemy.orm import selectinload

stmt = select(User).options(selectinload(User.team))
result = await session.execute(stmt)
users = result.scalars().all()
# Team data already loaded
```

**4. Batch Operations:**
```python
# ✅ Good - Batch insert
users = [User(...) for _ in range(100)]
session.add_all(users)
await session.commit()

# ❌ Bad - Individual inserts
for user_data in user_list:
    user = User(**user_data)
    session.add(user)
    await session.commit()  # 100 commits!
```

### Caching

**Use Redis for caching:**
```python
# ✅ Good - Cache expensive operations
cache_key = f"user:{user_id}"
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)

# Expensive operation
user = await get_user_from_db(session, user_id)

# Cache result
await redis.setex(cache_key, 3600, json.dumps(user.dict()))
return user
```

### Connection Pooling

**Tune connection pool:**
```python
# In database setup
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Number of connections
    max_overflow=10,  # Additional connections
    pool_pre_ping=True,  # Verify connections
)
```

---

## Best Practices

### ✅ DO

1. **Use async/await everywhere**
   ```python
   # ✅ Good - All async
   async def get_user(session: AsyncSession, user_id: UUID):
       user = await get_user_by_id(session, user_id)
       return user
   ```

2. **Use thread pool for blocking operations**
   ```python
   # ✅ Good - Offload blocking I/O
   data = await asyncio.to_thread(open("file.txt").read)
   ```

3. **Use connection pooling**
   ```python
   # ✅ Good - Reuse connections
   # Configured in database setup
   ```

4. **Use caching for expensive operations**
   ```python
   # ✅ Good - Cache results
   cached = await redis.get(cache_key)
   if cached:
       return cached
   ```

5. **Batch database operations**
   ```python
   # ✅ Good - Batch insert
   session.add_all(items)
   await session.commit()
   ```

### ❌ DON'T

1. **Don't block the event loop**
   ```python
   # ❌ Bad - Blocks event loop
   time.sleep(5)
   requests.get("https://api.example.com")
   open("file.txt").read()
   ```

2. **Don't use synchronous libraries**
   ```python
   # ❌ Bad - Synchronous library
   import requests
   response = requests.get(url)
   
   # ✅ Good - Async library
   import httpx
   response = await httpx.AsyncClient().get(url)
   ```

3. **Don't forget to await**
   ```python
   # ❌ Bad - Missing await
   result = session.execute(stmt)  # Returns coroutine, not result
   
   # ✅ Good - Awaited
   result = await session.execute(stmt)
   ```

4. **Don't create too many connections**
   ```python
   # ❌ Bad - Too many connections
   pool_size=1000  # Excessive
   
   # ✅ Good - Reasonable pool size
   pool_size=20  # Appropriate
   ```

---

## Troubleshooting

### Common Issues

**1. "Event loop is closed" error**
- Check if async operations are awaited
- Verify async context is maintained
- Check for blocking operations

**2. Slow performance**
- Check for blocking operations
- Verify database queries are optimized
- Check connection pool size
- Review caching strategy

**3. Connection pool exhaustion**
- Increase pool_size
- Check for connection leaks
- Verify connections are released
- Review connection timeout

**4. Deadlocks**
- Check for blocking operations
- Verify async/await usage
- Review database transaction isolation
- Check for circular dependencies

### Debugging

**Check for blocking operations:**
```python
import asyncio

# Enable debug mode
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # Windows
# Or use default on Linux/Mac

# Monitor event loop
loop = asyncio.get_event_loop()
print(f"Event loop: {loop}")
```

**Profile async operations:**
```python
import time

async def profile_operation():
    start = time.time()
    result = await expensive_operation()
    duration = time.time() - start
    logger.info(f"Operation took {duration}s")
    return result
```

---

## Next Steps

- Read [Background Jobs Documentation](./BACKGROUND_JOBS.md) for async job processing
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production tuning
- Read [Troubleshooting Guide](../10-troubleshooting/TROUBLESHOOTING.md) for common issues

---

**Status:** Async model documented, ready for implementation.
