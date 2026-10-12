# Append-Only Ledger
**Version:** 1.0.0  
**Last Updated:** 2026-07-28
---
## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Models](#database-models)
4. [Operations](#operations)
5. [API Endpoints](#api-endpoints)
6. [Configuration](#configuration)
7. [Events](#events)
8. [Usage Examples](#usage-examples)
9. [Best Practices](#best-practices)
---
## Overview
The append-only ledger provides an immutable account balance history for SwX-Core. It exists as a foundation for usage-based billing, credits, refunds, and other money-like movements where every balance change must stay traceable.
- **Append-only entries** mean `swx_ledger_entry` rows are created once and never updated or deleted
- **Running balance tracking** stores `balance_after` on every entry for fast audit review
- **Cached balance reads** use a separate balance table so the latest amount does not require replaying the full history
- **Idempotent payment flows** prevent duplicate credits, debits, refunds, and transfers when callers retry requests
---
## Architecture
The ledger follows the normal SwX route stack.
```text
Admin Route -> Controller -> Service -> Repository -> Models

/admin/ledger/*
    -> ledger_controller.py
        -> ledger_service.py
            -> ledger_repository.py
                -> LedgerEntry / LedgerBalance / IdempotencyRecord
```
The module uses three tables.
### `swx_ledger_entry`
Stores the immutable transaction history. Every credit, debit, refund, or transfer leg creates a new row.
### `swx_ledger_balance`
Stores the latest known balance per account for fast reads. The service updates it after successful writes.
### `swx_idempotency_record`
Stores processed idempotency keys and links each key to the ledger entry created for that request.
### Nano-units
Ledger amounts are stored as integers. The design expectation is nano-unit precision, for example `1 USD = 1,000,000,000` nano-units, which avoids floating point rounding problems in billing flows.
---
## Database Models
### `swx_ledger_entry`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `account_id` | UUID | Ledger account identifier, indexed |
| `entry_type` | string | Entry kind such as `credit`, `debit`, `refund`, or `adjustment` |
| `amount` | int | Integer amount in nano-units |
| `currency` | string | Currency code, defaults to `USD` |
| `reference_type` | string, nullable | Business reference category |
| `reference_id` | string, nullable | External or related object identifier |
| `idempotency_key` | string, nullable | Retry-safe request key, indexed |
| `description` | string, nullable | Human readable note |
| `metadata` | JSONB | Structured extra data stored in the `metadata_` field on the model |
| `balance_after` | int | Running balance after this entry is applied |
| `created_at` | datetime | Creation timestamp |
| `created_by` | UUID, nullable | Optional user that triggered the entry |
`LedgerEntry` is immutable by design. Reads can trust `balance_after` as the historical running total at that point in time.
### `swx_ledger_balance`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `account_id` | UUID | Unique account identifier |
| `currency` | string | Cached currency code |
| `balance` | int | Latest cached balance |
| `last_entry_id` | UUID, nullable | Most recent ledger entry applied to the cache |
| `updated_at` | datetime | Last cache update timestamp |
### `swx_idempotency_record`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `key` | string | Unique idempotency key |
| `account_id` | UUID | Account tied to the request |
| `entry_id` | UUID, nullable | Ledger entry created for the key |
| `status` | string | Current record state, defaults to `completed` |
| `created_at` | datetime | Creation timestamp |
### Enums
`EntryType` values in `swx_core/models/ledger.py`:
| Value | Meaning |
|---|---|
| `CREDIT` | Adds value to an account |
| `DEBIT` | Removes value from an account |
| `REFUND` | Returns value from a previous debit |
| `ADJUSTMENT` | General adjustment marker |
`ReferenceType` values in `swx_core/models/ledger.py`:
| Value | Meaning |
|---|---|
| `TOPUP` | Funding or recharge source |
| `USAGE` | Consumption or usage event |
| `REFUND` | Refund reference |
| `ADJUSTMENT` | Manual or system adjustment |
| `EXPIRY` | Expired credit reference |
---
## Operations
All write operations support idempotency keys. The service checks `swx_idempotency_record` first and returns the original result for repeated requests.
### Credit
Adds funds to an account, creates a `credit` entry, updates the cached balance, and emits `ledger.credit`.
### Debit
Deducts funds from an account, creates a `debit` entry, and updates the cached balance. If `LEDGER_ALLOW_NEGATIVE_BALANCE` is `False`, the service raises `HTTPException(status_code=400, detail="Insufficient ledger balance")` when funds are not enough.
### Refund
Reverses a previous debit by creating a new `refund` entry for the same amount. `refund()` requires `account_id`, the original debit `entry_id`, and an `idempotency_key`. The new entry stores `reference_type="refund"` and `reference_id=str(original_entry_id)`.
### Transfer
Moves funds between two accounts in one database transaction. The service creates a debit leg on `from_account_id` and a credit leg on `to_account_id`. If either write fails, the transaction rolls back so both legs fail together.
### Reconcile
Compares the cached balance in `swx_ledger_balance` with a computed balance from ledger entries. The response includes `cached_balance`, `computed_balance`, and `matches`.
---
## API Endpoints
All admin ledger routes require `get_current_admin_user` and live under `/admin/ledger`.
| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/ledger/credit` | Create a credit entry from `CreditRequest` |
| `POST` | `/admin/ledger/debit` | Create a debit entry from `DebitRequest` |
| `POST` | `/admin/ledger/refund` | Refund a prior debit using query params `account_id`, `original_entry_id`, and `idempotency_key` |
| `POST` | `/admin/ledger/transfer` | Transfer funds using `TransferRequest` |
| `GET` | `/admin/ledger/{account_id}/balance` | Get the cached or reconstructed current balance |
| `GET` | `/admin/ledger/{account_id}/entries` | List entry history with `skip` and `limit` |
| `GET` | `/admin/ledger/{account_id}/reconcile` | Compare cached and computed balances |
---
## Configuration
Ledger behavior is controlled in `swx_core/config/settings.py`.
```python
LEDGER_ENABLED: bool = Field(
    default=True, description="Enable append-only ledger framework"
)
LEDGER_BALANCE_CACHE_TTL: int = Field(
    default=300, description="TTL in seconds for ledger balance cache"
)
LEDGER_ALLOW_NEGATIVE_BALANCE: bool = Field(
    default=False, description="Allow balances to go negative"
)
```
- **`LEDGER_ENABLED`**: Global feature switch for the ledger module.
- **`LEDGER_BALANCE_CACHE_TTL`**: Configured TTL value for ledger balance caching.
- **`LEDGER_ALLOW_NEGATIVE_BALANCE`**: When `False`, debits and transfer debits fail on insufficient balance.
---
## Events
The ledger service dispatches events through `swx_core.events.event_bus`.
| Event name | Payload | When emitted |
|---|---|---|
| `ledger.credit` | `{"account_id": str(account_id), "entry_id": str(entry.id), "amount": amount}` | After `credit()` commits, and after the credit leg of `transfer()` commits |
| `ledger.debit` | `{"account_id": str(account_id), "entry_id": str(entry.id), "amount": amount}` | After `debit()` commits, and after the debit leg of `transfer()` commits |
| `ledger.refund` | `{"account_id": str(account_id), "entry_id": str(entry.id), "original_entry_id": str(original_entry_id)}` | After `refund()` commits |
---
## Usage Examples
The service layer lives in `swx_core/services/ledger_service.py`.
### Crediting an Account
```python
from uuid import UUID

from swx_core.models.ledger import CreditRequest, ReferenceType
from swx_core.services import ledger_service

account_id = UUID("11111111-1111-1111-1111-111111111111")

credit_entry = await ledger_service.credit(
    session=session,
    request=CreditRequest(
        account_id=account_id,
        amount=5_000_000_000,
        currency="USD",
        reference_type=ReferenceType.TOPUP.value,
        reference_id="topup_20260728_001",
        idempotency_key="ledger-credit-001",
        description="Initial wallet top-up",
    ),
)
```
### Debiting an Account
```python
from swx_core.models.ledger import DebitRequest, ReferenceType
from swx_core.services import ledger_service

debit_entry = await ledger_service.debit(
    session=session,
    request=DebitRequest(
        account_id=account_id,
        amount=1_250_000_000,
        currency="USD",
        reference_type=ReferenceType.USAGE.value,
        reference_id="usage_job_123",
        idempotency_key="ledger-debit-001",
        description="Deduct usage charges",
    ),
)
```
`credit_entry.balance_after` and `debit_entry.balance_after` expose the running total after each operation.
---
## Best Practices
- Always send an `idempotency_key` for payment, top-up, refund, and transfer requests.
- Store and pass amounts as integer nano-units, not floats or decimals in application logic.
- Run `reconcile()` on a schedule so cached balances stay trustworthy.
- Treat `swx_ledger_entry` as immutable and create compensating entries instead of editing history.
- Use `reference_type` and `reference_id` consistently so usage, refunds, and top-ups can be traced later.
---
**Status:** Append-only ledger documented, ready for use.
