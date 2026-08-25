# Session Management: Avoiding the DB-HTTP Deadlock

## The Problem

SwX uses `SessionDep` — a request-scoped `AsyncSession` — as the standard
database dependency for FastAPI routes. The session is created when the
request starts and closed when the request ends.

This is safe for routes that only do database work. But when a route
**reads from the database and then makes an outbound HTTP call** (e.g.
calling Paystack, Flutterwave, or Stripe), the database connection is held
open for the entire duration of the HTTP call.

Under load:

```
pool_size (e.g. 10) × slow HTTP calls (e.g. 30s each)
  = connection pool exhaustion
  = new requests hang indefinitely waiting for a connection
  = application deadlock
```

### Evidence

| Route | Behavior | Why |
|-------|----------|-----|
| `POST /payments/initialize` (existing) | Works | Takes `amount_nano` from the request body — does **zero DB reads** after auth. The `UserDep` session sits idle. |
| `POST /payments/initialize/plan` (custom, pre-fix) | Hangs | `require_permission` + `SessionDep` start a transaction, then the handler calls Paystack. Connection held during HTTP. |

---

## The Three Correct Patterns

### Pattern A — Separate Session for DB Reads

Use when you control the route handler and need a DB read before an HTTP call.

```python
from swx_core.database.db import AsyncSessionLocal

async def my_route(current_user: UserDep, body: MyRequest):
    # DB read on a short-lived session (committed and closed)
    async with AsyncSessionLocal() as read_session:
        repo = BaseRepository(model=MyModel, session=read_session)
        data = await repo.find_by(...)

    # Outbound HTTP call with no open DB transaction
    result = await http_client.post(...)
    return result
```

### Pattern B — `with_read_session()` Helper (Recommended)

Use the framework-provided helper for the same pattern. It is clearer and
self-documenting.

```python
from swx_core.database.session_helpers import with_read_session

async def my_controller(item_key, provider, ...):
    async with with_read_session() as session:
        item = await repository.get_by_key(session, item_key)
        if item is None:
            raise NotFoundError("Item", item_key)
        item_amount = item.amount
        item_currency = item.currency

    # Session is now closed — safe to make the outbound HTTP call.
    return await get_local_payment_provider(provider).initialize_payment(
        item_amount, item_currency, email, reference, callback_url
    )
```

The route handler for this controller takes **only `UserDep`** (for the
email) — no `SessionDep`:

```python
@router.post("/payments/initialize/item")
async def initialize_payment_for_item(
    body: ItemRequest, current_user: UserDep
) -> dict[str, object]:
    return await billing_controller.initialize_payment_for_item_controller(
        item_key=body.item_key,
        provider=body.provider,
        callback_url=body.callback_url,
        email=current_user.email,
    )
```

### Pattern C — Native Controller Session Management

The controller itself manages the session lifecycle. This is what the
server-side validated payment initialization endpoints use
(`initialize_payment_for_plan_controller`,
`initialize_payment_for_pack_controller`).

The controller opens a short-lived session via `with_read_session()`,
looks up the price, closes the session, then calls the provider. The route
handler never touches `SessionDep`.

---

## When Each Pattern Applies

| Scenario | Pattern | Why |
|----------|---------|-----|
| Route does DB reads only (no HTTP) | `SessionDep` (default) | No deadlock risk — session closes when request ends. |
| Route does DB read then HTTP call | B or C | Session must close before the HTTP call. |
| Webhook handler credits wallet | `AsyncSessionLocal()` directly | No `SessionDep` on webhook routes (no auth dep). Open a session, do the work, close it. |
| Background job / Celery task | `AsyncSessionLocal()` directly | No request lifecycle — manage the session yourself. |

---

## `BaseRepository.find_by()` Warning

`BaseRepository` uses `_session_context()` — an `asynccontextmanager` that
yields the injected session if provided, or creates a new one if not.

When you inject a `SessionDep` session into `BaseRepository` and then make
an outbound HTTP call **after** the `find_by()` returns, the injected
session is still open (it's the request-scoped session). This is the
deadlock pattern.

**Do not** do this:

```python
# DANGEROUS — session held during HTTP call
@router.post("/dangerous")
async def dangerous_route(session: SessionDep, current_user: UserDep):
    repo = BaseRepository(model=Plan, session=session)
    plan = await repo.find_by(key="pro_v1")  # starts a transaction on session

    # session is STILL OPEN — connection held during this HTTP call
    result = await httpx.post("https://api.paystack.co/transaction/initialize", ...)

    return result
```

**Do** this instead:

```python
# SAFE — session closed before HTTP call
@router.post("/safe")
async def safe_route(current_user: UserDep, body: PlanRequest):
    return await billing_controller.initialize_payment_for_plan_controller(
        plan_key=body.plan_key,
        provider=body.provider,
        callback_url=body.callback_url,
        email=current_user.email,
    )
# The controller uses with_read_session() internally.
```

---

## `UserDep` and Caching

`UserDep` (`get_current_user`) depends on `SessionDep`. When
`USER_CACHE_ENABLED=True` (recommended), the user is fetched from Redis
on cache hit — no DB query, no open transaction. When the cache misses,
a DB query runs on the `SessionDep` session, but the session is only
active for the duration of the query, not the entire request.

However, the `SessionDep` session **is** still open for the entire request
lifecycle (it's a dependency). If your route does additional DB reads on
this session and then makes an HTTP call, you're back in the deadlock
pattern.

**Recommendation:** Enable `USER_CACHE_ENABLED=True` (requires Redis) to
avoid per-request DB queries for user resolution. For routes that mix DB
reads with HTTP calls, use Pattern B or C — do not read from the
`UserDep` session.
