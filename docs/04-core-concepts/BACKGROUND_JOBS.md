# Background Jobs

**Version:** 1.0.0  
**Last Updated:** 2026-01-26  
**Updated:** Job handlers fully implemented

---

## Table of Contents

1. [Overview](#overview)
2. [Job Lifecycle](#job-lifecycle)
3. [Job Types](#job-types)
4. [Retry Behavior](#retry-behavior)
5. [Idempotency](#idempotency)
6. [Usage Examples](#usage-examples)
7. [Creating Job Handlers](#creating-job-handlers)
8. [Observability](#observability)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **robust background job system** for processing asynchronous tasks. Jobs are:

- **Idempotent** - Safe to retry
- **Retryable** - Automatic retries with exponential backoff
- **Observable** - Full status tracking and audit logging
- **Locked** - Database-level locking prevents double execution
- **Prioritized** - Priority-based execution order

### Key Features

- ✅ **Database-backed** - Jobs stored in PostgreSQL
- ✅ **Locking** - Prevents double execution across workers
- ✅ **Retries** - Exponential backoff for failed jobs
- ✅ **Dead-letter Queue** - Failed jobs moved to dead-letter
- ✅ **Priority** - Higher priority jobs execute first
- ✅ **Scheduling** - Jobs can be scheduled for future execution
- ✅ **Audit Logging** - All job events logged

---

## Job Lifecycle

### Job States

```
PENDING → QUEUED → RUNNING → COMPLETED
                              ↓
                           FAILED → QUEUED (retry) → ... → DEAD_LETTER
                              ↓
                           CANCELLED
```

**State Transitions:**

1. **PENDING** - Job created, not yet queued
2. **QUEUED** - Job ready for execution
3. **RUNNING** - Job currently executing
4. **COMPLETED** - Job completed successfully
5. **FAILED** - Job failed (may retry)
6. **DEAD_LETTER** - Job failed after max attempts
7. **CANCELLED** - Job cancelled before execution

### Lifecycle Flow

```
1. Job Created
   └── Status: PENDING
   └── Scheduled for execution

2. Job Runner Polls
   └── Finds PENDING/QUEUED jobs
   └── Locks job (status: RUNNING)

3. Handler Executes
   └── Job handler processes payload
   └── Returns result or raises exception

4. Success Path
   └── Status: COMPLETED
   └── Result stored
   └── Audit logged

5. Failure Path
   └── Check attempts < max_attempts
   ├── Yes: Retry (status: QUEUED, scheduled_at = now + backoff)
   └── No: Dead-letter (status: DEAD_LETTER)
```

---

## Job Types

### Built-in Job Types

**Billing Jobs:**
- `billing.sync` - Sync billing data with provider
- `billing.webhook` - Process billing webhook
- `billing.subscription.renewal` - Renew subscription

**Alert Jobs:**
- `alert.send` - Send alert via channel
- `alert.aggregate` - Aggregate alerts

**Audit Jobs:**
- `audit.aggregate` - Aggregate audit logs
- `audit.cleanup` - Cleanup old audit logs

**System Jobs:**
- `system.cache.refresh` - Refresh cache
- `system.data.export` - Export data

**Generic:**
- `generic` - Generic job type

### Job Model

```python
class Job(SQLModel, table=True):
    id: UUID
    job_type: str  # "billing.sync"
    payload: Dict[str, Any]  # Job data
    status: JobStatus  # PENDING, QUEUED, RUNNING, etc.
    attempts: int  # Current attempt number
    max_attempts: int  # Maximum retry attempts (default: 3)
    scheduled_at: Optional[datetime]  # When to execute
    locked_at: Optional[datetime]  # When locked
    locked_by: Optional[str]  # Worker ID
    started_at: Optional[datetime]  # When execution started
    completed_at: Optional[datetime]  # When execution completed
    last_error: Optional[Dict]  # Last error details
    result: Optional[Dict]  # Job result
    priority: int  # Lower = higher priority (default: 100)
    tags: List[str]  # Job tags
    created_at: datetime
    updated_at: datetime
```

---

## Retry Behavior

### Exponential Backoff

**Backoff Formula:**
```python
backoff_seconds = 2 ** attempts
# Attempt 1: 2 seconds
# Attempt 2: 4 seconds
# Attempt 3: 8 seconds
# Attempt 4: 16 seconds
# ...
```

**Example:**
```python
# Job fails on attempt 1
# Scheduled for retry in 2 seconds (attempt 2)
# Job fails on attempt 2
# Scheduled for retry in 4 seconds (attempt 3)
# Job fails on attempt 3
# Max attempts reached → DEAD_LETTER
```

### Max Attempts

**Default:** 3 attempts

**Configurable:**
```python
job = Job(
    job_type="billing.sync",
    payload={...},
    max_attempts=5  # Custom max attempts
)
```

### Retry Conditions

**Jobs are retried if:**
- Handler raises exception
- Attempts < max_attempts
- Job not cancelled

**Jobs are NOT retried if:**
- Attempts >= max_attempts (moved to dead-letter)
- Job is cancelled
- Handler returns successfully

---

## Idempotency

### Why Idempotency?

**Jobs may be executed multiple times:**
- Retries after failures
- Worker crashes during execution
- Lock timeout releases job

**Idempotent jobs are safe to retry.**

### Making Jobs Idempotent

**1. Check Before Action:**
```python
async def billing_sync_handler(session: AsyncSession, payload: Dict) -> Dict:
    subscription_id = payload["subscription_id"]
    
    # Check if already synced
    subscription = await get_subscription(session, subscription_id)
    if subscription.last_synced_at and subscription.last_synced_at > datetime.utcnow() - timedelta(minutes=5):
        return {"status": "already_synced", "skipped": True}
    
    # Perform sync
    await sync_subscription(session, subscription)
    return {"status": "synced"}
```

**2. Use Unique Constraints:**
```python
async def create_resource_handler(session: AsyncSession, payload: Dict) -> Dict:
    resource_id = payload["resource_id"]
    
    # Check if exists
    existing = await get_resource(session, resource_id)
    if existing:
        return {"status": "exists", "resource_id": str(existing.id)}
    
    # Create resource
    resource = await create_resource(session, payload)
    return {"status": "created", "resource_id": str(resource.id)}
```

**3. Use Idempotency Keys:**
```python
async def process_payment_handler(session: AsyncSession, payload: Dict) -> Dict:
    idempotency_key = payload["idempotency_key"]
    
    # Check if already processed
    existing = await get_payment_by_key(session, idempotency_key)
    if existing:
        return {"status": "already_processed", "payment_id": str(existing.id)}
    
    # Process payment
    payment = await process_payment(session, payload)
    return {"status": "processed", "payment_id": str(payment.id)}
```

---

## Usage Examples

### Creating Jobs

**Via API:**
```bash
POST /api/admin/job/
{
  "job_type": "billing.sync",
  "payload": {
    "subscription_id": "sub-123"
  },
  "max_attempts": 5,
  "priority": 50
}
```

**Via Code:**
```python
from swx_core.models.job import Job, JobStatus
from swx_core.services.job_service import create_job

job = await create_job(
    session,
    job_type="billing.sync",
    payload={"subscription_id": "sub-123"},
    max_attempts=5,
    priority=50
)
```

**Scheduled Jobs:**
```python
from datetime import datetime, timedelta

job = await create_job(
    session,
    job_type="system.cache.refresh",
    payload={},
    scheduled_at=datetime.utcnow() + timedelta(hours=1)  # Execute in 1 hour
)
```

### Querying Jobs

**Get Job Status:**
```bash
GET /api/admin/job/{job_id}
```

**List Jobs:**
```bash
GET /api/admin/job/?status=running&job_type=billing.sync&limit=100
```

**Get Job Stats:**
```bash
GET /api/admin/job/stats
```

### Retrying Jobs

**Manual Retry:**
```bash
POST /api/admin/job/{job_id}/retry
```

**Via Code:**
```python
from swx_core.services.job_service import retry_job

await retry_job(session, job_id)
```

---

## Creating Job Handlers

### Handler Structure

**Handler Signature:**
```python
async def job_handler(
    session: AsyncSession,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process job payload.
    
    Args:
        session: Database session
        payload: Job payload data
    
    Returns:
        Result dictionary
    
    Raises:
        Exception: If job fails (will be retried)
    """
    # Process job
    result = await process_payload(session, payload)
    return {"status": "success", "result": result}
```

### Registering Handlers

**At Startup:**
```python
# swx_core/main.py

from swx_core.services.job import register_job_handler
from swx_core.services.job.handlers import billing_sync_handler
from swx_core.models.job import JobType

register_job_handler(JobType.BILLING_SYNC, billing_sync_handler)
```

**Custom Handler:**
```python
# swx_app/services/job_handlers.py

from swx_core.services.job import register_job_handler

async def custom_job_handler(session: AsyncSession, payload: Dict) -> Dict:
    """Custom job handler."""
    # Process job
    result = await process_custom_job(session, payload)
    return {"status": "success", "result": result}

# Register
register_job_handler("custom.job.type", custom_job_handler)
```

### Example Handlers

**Billing Sync Handler:**
```python
async def billing_sync_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sync billing account with external provider (e.g., Stripe)."""
    account_id_str = payload.get("account_id")
    if not account_id_str:
        raise ValueError("account_id is required")
    
    account_id = uuid.UUID(account_id_str) if isinstance(account_id_str, str) else account_id_str
    
    # Fetch account from database
    stmt = select(BillingAccount).where(BillingAccount.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        return {"status": "error", "message": "Account not found", "account_id": str(account_id)}
    
    # Get active subscription
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    
    if not subscription or not subscription.stripe_subscription_id:
        return {"status": "skipped", "account_id": str(account_id), "reason": "No Stripe subscription"}
    
    # Sync with Stripe
    provider = get_stripe_provider()
    # In a real implementation, fetch subscription from Stripe and update local status
    
    return {
        "status": "synced",
        "account_id": str(account_id),
        "subscription_id": str(subscription.id),
        "stripe_subscription_id": subscription.stripe_subscription_id
    }
```

**Billing Webhook Handler:**
```python
async def billing_webhook_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process webhook events from billing provider (e.g., Stripe)."""
    event_type = payload.get("event_type")
    event_data = payload.get("event_data", {})
    
    subscription_service = SubscriptionService(session)
    
    # Handle different webhook event types
    if event_type == "customer.subscription.updated":
        stripe_subscription_id = event_data.get("id")
        status = event_data.get("status")
        
        # Find subscription by Stripe ID
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()
        
        if subscription:
            # Map Stripe status to our status
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "canceled": SubscriptionStatus.CANCELED,
                "past_due": SubscriptionStatus.PAST_DUE,
            }
            new_status = status_map.get(status, SubscriptionStatus.ACTIVE)
            
            if subscription.status != new_status:
                subscription.status = new_status
                if new_status == SubscriptionStatus.CANCELED:
                    subscription.ended_at = datetime.utcnow()
                session.add(subscription)
                await session.commit()
    
    return {"processed": True, "event_type": event_type}
```

**Alert Send Handler:**
```python
async def alert_send_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send alert notification via specified channel."""
    alert_id = payload.get("alert_id")
    channel = payload.get("channel", "email")
    
    # Extract alert details from payload
    severity = AlertSeverity(payload.get("severity", "INFO"))
    source = AlertSource(payload.get("source", "SYSTEM"))
    event_type = payload.get("event_type", "ALERT")
    message = payload.get("message", "Alert notification")
    metadata = payload.get("metadata", {})
    
    # Create alert object
    alert = Alert(
        severity=severity,
        source=source,
        event_type=event_type,
        message=message,
        environment=payload.get("environment", "production"),
        actor_type=AlertActorType(payload.get("actor_type", "NONE")),
        actor_id=payload.get("actor_id"),
        resource_type=payload.get("resource_type"),
        resource_id=payload.get("resource_id"),
        metadata=metadata
    )
    
    # Send via specific channel
    channel_map = {
        "log": LogChannel(),
        "slack": SlackChannel(),
        "email": EmailChannel(),
        "sms": SmsChannel()
    }
    
    channel_instance = channel_map.get(channel)
    if channel_instance:
        success = await channel_instance.send(alert)
        return {"sent": success, "alert_id": alert_id, "channel": channel}
    
    return {"sent": False, "alert_id": alert_id, "channel": channel, "reason": "Unknown channel"}
```

**Audit Aggregate Handler:**
```python
async def audit_aggregate_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate audit logs for reporting and analysis."""
    from datetime import datetime, timedelta
    from sqlmodel import func, desc
    
    # Parse date range
    date_from_str = payload.get("date_from")
    date_to_str = payload.get("date_to")
    
    date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00")) if date_from_str else datetime.utcnow() - timedelta(days=7)
    date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00")) if date_to_str else datetime.utcnow()
    
    # Aggregate by action, resource_type, outcome
    stmt = (
        select(
            AuditLog.action,
            AuditLog.resource_type,
            AuditLog.outcome,
            func.count(AuditLog.id).label("count")
        )
        .where(
            and_(
                AuditLog.timestamp >= date_from,
                AuditLog.timestamp <= date_to
            )
        )
        .group_by(AuditLog.action, AuditLog.resource_type, AuditLog.outcome)
        .order_by(desc("count"))
    )
    result = await session.execute(stmt)
    aggregates = result.all()
    
    # Total count
    stmt_total = (
        select(func.count(AuditLog.id))
        .where(
            and_(
                AuditLog.timestamp >= date_from,
                AuditLog.timestamp <= date_to
            )
        )
    )
    result_total = await session.execute(stmt_total)
    total_count = result_total.scalar() or 0
    
    return {
        "aggregated": True,
        "records": total_count,
        "results": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "total_records": total_count,
            "by_action": [
                {
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "outcome": row.outcome,
                    "count": row.count
                }
                for row in aggregates
            ]
        }
    }
```

**Cache Refresh Handler:**
```python
async def cache_refresh_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh application cache (settings, permissions, etc.)."""
    cache_type = payload.get("cache_type", "all")
    
    refreshed_items = []
    
    if cache_type == "all" or cache_type == "settings":
        # Refresh settings cache
        from swx_core.services.settings_service import SettingsService
        SettingsService.invalidate_cache()
        refreshed_items.append("settings")
        
        # Warm cache by pre-loading common settings
        settings_service = SettingsService(session)
        common_keys = [
            "auth.access_token_expire_minutes",
            "auth.refresh_token_expire_days",
            "system.environment"
        ]
        for key in common_keys:
            try:
                await settings_service.get(key, None)
            except Exception:
                pass  # Ignore errors for missing settings
    
    return {
        "refreshed": True,
        "cache_type": cache_type,
        "refreshed_items": refreshed_items
    }
```

---

## Observability

### Job Status Tracking

**Query Job Status:**
```python
from swx_core.repositories.job_repository import get_job_by_id

job = await get_job_by_id(session, job_id)
print(f"Status: {job.status}")
print(f"Attempts: {job.attempts}/{job.max_attempts}")
print(f"Last Error: {job.last_error}")
print(f"Result: {job.result}")
```

### Audit Logging

**All job events are audit logged:**
- Job created
- Job started
- Job completed
- Job failed
- Job retried
- Job moved to dead-letter

**Example:**
```python
# Automatically logged by job runner
await audit.log_event(
    action="job.completed",
    actor_type=ActorType.SYSTEM,
    actor_id=worker_id,
    resource_type="job",
    resource_id=str(job.id),
    outcome=AuditOutcome.SUCCESS,
    context={"job_type": job.job_type, "attempts": job.attempts}
)
```

### Monitoring

**Key Metrics:**
- Jobs created per hour
- Jobs completed per hour
- Jobs failed per hour
- Average execution time
- Dead-letter queue size

**Queries:**
```sql
-- Jobs by status
SELECT status, COUNT(*) 
FROM job 
GROUP BY status;

-- Failed jobs
SELECT job_type, COUNT(*) 
FROM job 
WHERE status = 'dead_letter'
GROUP BY job_type;

-- Average execution time
SELECT 
    job_type,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds
FROM job
WHERE status = 'completed'
GROUP BY job_type;
```

---

## Best Practices

### ✅ DO

1. **Make handlers idempotent**
   ```python
   # ✅ Good - Check before action
   existing = await get_resource(session, resource_id)
   if existing:
       return {"status": "exists"}
   
   # Create resource
   ...
   ```

2. **Handle errors gracefully**
   ```python
   # ✅ Good - Specific error handling
   try:
       result = await process_payment(session, payload)
   except PaymentProviderError as e:
       # Retryable error
       raise
   except ValidationError as e:
       # Non-retryable error
       raise ValueError(f"Invalid payload: {e}")
   ```

3. **Set appropriate max_attempts**
   ```python
   # ✅ Good - Based on job type
   max_attempts = 5  # For critical jobs
   max_attempts = 3  # For normal jobs
   max_attempts = 1  # For non-retryable jobs
   ```

4. **Use priority for urgent jobs**
   ```python
   # ✅ Good - Lower priority = higher urgency
   priority = 10   # Urgent
   priority = 50   # Normal
   priority = 100  # Low priority
   ```

5. **Include useful payload data**
   ```python
   # ✅ Good - Complete payload
   payload = {
       "subscription_id": str(subscription.id),
       "action": "sync",
       "timestamp": datetime.utcnow().isoformat()
   }
   ```

### ❌ DON'T

1. **Don't make handlers blocking**
   ```python
   # ❌ Bad - Blocks event loop
   import time
   time.sleep(10)  # DON'T DO THIS
   
   # ✅ Good - Use async sleep
   await asyncio.sleep(10)
   ```

2. **Don't ignore errors**
   ```python
   # ❌ Bad - Errors swallowed
   try:
       await process_job(session, payload)
   except Exception:
       pass  # Error ignored
   
   # ✅ Good - Errors raised for retry
   try:
       await process_job(session, payload)
   except Exception as e:
       logger.error(f"Job failed: {e}")
       raise  # Will be retried
   ```

3. **Don't store large payloads**
   ```python
   # ❌ Bad - Large payload
   payload = {
       "large_data": "..." * 1000000  # Too large
   }
   
   # ✅ Good - Store reference
   payload = {
       "data_id": str(data.id)  # Reference to data
   }
   ```

---

## Troubleshooting

### Common Issues

**1. Jobs not executing**
- Check job runner is started
- Verify handlers are registered
- Check job status (should be QUEUED)
- Verify database connection

**2. Jobs stuck in RUNNING**
- Check for worker crashes
- Verify lock timeout is appropriate
- Check for dead workers
- Manually release stale locks

**3. Jobs failing repeatedly**
- Check handler errors
- Verify payload is correct
- Check for non-retryable errors
- Review dead-letter queue

**4. Jobs executing multiple times**
- Verify locking is working
- Check for multiple workers
- Verify `with_for_update(skip_locked=True)` is used
- Check lock timeout

### Debugging

**Check job status:**
```python
from swx_core.repositories.job_repository import get_job_by_id

job = await get_job_by_id(session, job_id)
print(f"Status: {job.status}")
print(f"Attempts: {job.attempts}/{job.max_attempts}")
print(f"Last Error: {job.last_error}")
```

**List running jobs:**
```python
from swx_core.models.job import Job, JobStatus
from sqlmodel import select

stmt = select(Job).where(Job.status == JobStatus.RUNNING)
result = await session.execute(stmt)
running_jobs = result.scalars().all()
```

**Check dead-letter queue:**
```python
stmt = select(Job).where(Job.status == JobStatus.DEAD_LETTER)
result = await session.execute(stmt)
dead_letter_jobs = result.scalars().all()
```

---

## Next Steps

- Read [Async Model Documentation](./ASYNC_MODEL.md) for async patterns
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup
- Read [Troubleshooting Guide](../10-troubleshooting/TROUBLESHOOTING.md) for common issues

---

**Status:** Background jobs documented, ready for implementation.
