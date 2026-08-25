"""Session helpers for the DB-read-then-HTTP pattern.

The request-scoped ``SessionDep`` holds a database connection for the entire
request lifecycle.  When a route handler performs a DB read on that session
and then makes an outbound HTTP call (e.g. to Paystack), the connection is
held open for the duration of the HTTP call.  Under load this exhausts the
connection pool and deadlocks the application.

These helpers provide short-lived sessions that are closed **before** the
caller performs any outbound I/O, breaking the deadlock.

Typical usage (controller manages its own session)::

    from swx_core.database.session_helpers import with_read_session

    async def initialize_payment_for_plan_controller(plan_key, provider, ...):
        async with with_read_session() as session:
            plan = await billing_repository.get_plan_by_key(session, plan_key)
            if plan is None:
                raise NotFoundError("Plan", plan_key)
            plan_amount = plan.amount
            plan_currency = plan.currency
        # Session is now closed — safe to make the outbound HTTP call.
        return await _call_provider_with_amount(
            "plan", plan_key, plan_amount, plan_currency, provider, ...
        )
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database.db import AsyncSessionLocal


@asynccontextmanager
async def with_read_session() -> AsyncIterator[AsyncSession]:
    """Yield a short-lived ``AsyncSession`` for DB reads that must close before outbound I/O.

    The session is created from the same ``AsyncSessionLocal`` factory as
    ``SessionDep`` but is **not** tied to the request lifecycle.  It closes
    as soon as the ``async with`` block exits, releasing the connection back
    to the pool before the caller makes any HTTP call.

    Yields:
        An ``AsyncSession`` ready for read queries.
    """
    async with AsyncSessionLocal() as session:
        yield session


__all__ = ["with_read_session"]
