# Multi-Currency Billing

Multi-currency support for African and global markets with local payment providers (Paystack, Flutterwave, M-Pesa), exchange rate management, per-jurisdiction tax calculation, and wallet integration with the append-only ledger.

---

## Overview

| Component | Description |
|-----------|-------------|
| **Currency** | Configurable currency registry (USD, NGN, KES, ZAR, GHS + custom) |
| **ExchangeRate** | Historical rate storage with direct, inverse, and pivot-based resolution |
| **Wallet** | Per-account, per-currency balance tracking — each wallet maps to its own ledger account |
| **Payment Providers** | Paystack (NG, GH), Flutterwave (NG, KE, ZA, GH), M-Pesa (KE) |
| **Tax Engine** | Country-specific VAT/rate lookup (NG 7.5%, KE 16%, ZA 15%, GH 15%, GB 20%) |

All amounts are stored in **nano-units** (integers) to avoid floating-point rounding errors.

---

## Database Tables

### `swx_currency`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `code` | String(3) | ISO 4217 code, unique (e.g. `USD`, `NGN`) |
| `name` | String(100) | Display name |
| `symbol` | String(10) | Currency symbol |
| `decimals` | Integer | Decimal places (default 2) |
| `is_base` | Boolean | Marks the base currency for conversion |
| `status` | String(20) | `active` or `disabled` |
| `minimum_amount` | Integer | Minimum transaction amount in nano-units |
| `supported_providers` | JSONB | List of provider names that accept this currency |
| `metadata` | JSONB | Extension data |

### `swx_exchange_rate`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `base_currency` | String(3) | Source currency code |
| `quote_currency` | String(3) | Target currency code |
| `rate` | Float | Exchange rate (base → quote) |
| `source` | String(50) | Rate source (e.g. `manual`, `api`) |
| `fetched_at` | DateTime | When the rate was fetched |

### `swx_wallet`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (also used as `account_id` in the ledger) |
| `account_id` | UUID | Owning user/account |
| `currency` | String(3) | Wallet currency code |
| `balance` | BigInteger | Balance in nano-units |
| `is_active` | Boolean | Wallet enabled flag |
| `metadata` | JSONB | Extension data |

---

## Exchange Rate Resolution

The exchange rate service uses a three-tier fallback:

1. **Direct rate** — looks up `base → quote` in `swx_exchange_rate`
2. **Inverse rate** — looks up `quote → base` and computes `1 / rate`
3. **Pivot rate** — finds a common base currency (default USD) and computes cross-rate via `pivot_rates[quote] / pivot_rates[base]`

```python
from swx_core.services.billing import exchange_rate_service

rate = await exchange_rate_service.get_rate(session, "USD", "NGN")  # → 1500.0
nano_amount = await exchange_rate_service.convert(session, 1_000_000_000, "USD", "NGN")  # → 1_500_000_000_000
```

---

## Wallet Operations

Each wallet uses its own `wallet.id` as the ledger `account_id`, ensuring per-currency balance isolation. All wallet mutations create append-only ledger entries.

```python
from swx_core.services.billing import wallet_service

wallet = await wallet_service.get_or_create_wallet(session, user_id, "NGN")
wallet = await wallet_service.credit_wallet(session, user_id, "NGN", amount_nano, reference, idempotency_key)
wallet = await wallet_service.debit_wallet(session, user_id, "NGN", amount_nano, reference, idempotency_key)
from_wallet, to_wallet = await wallet_service.transfer(session, user_id, "USD", "NGN", amount_nano, idempotency_key)
```

### Events

| Event | Payload |
|-------|---------|
| `wallet.credit` | `wallet_id`, `account_id`, `currency`, `amount`, `reference` |
| `wallet.debit` | `wallet_id`, `account_id`, `currency`, `amount`, `reference` |
| `wallet.transfer` | `account_id`, `from_currency`, `to_currency`, `amount`, `converted_amount` |

---

## Tax Calculation

Country-specific VAT/tax rates are stored in a static registry:

```python
from swx_core.services.billing import tax_service

result = tax_service.calculate_tax(amount_nano=1_000_000_000, jurisdiction="NG")
# → {"amount": 1_000_000_000, "tax_rate": 7.5, "tax_amount": 75_000_000, "total": 1_075_000_000}

tax_service.get_supported_jurisdictions()
# → {"NG": 7.5, "KE": 16.0, "ZA": 15.0, "GH": 15.0, "US": 0.0, "GB": 20.0}
```

---

## Payment Providers

### Configuration

Credentials are stored as `${ENV_VAR}` placeholders in settings, resolved at runtime:

```python
# settings.py
PAYSTACK_SECRET_KEY: str = "${PAYSTACK_SECRET_KEY}"
FLUTTERWAVE_SECRET_KEY: str = "${FLUTTERWAVE_SECRET_KEY}"
MPESA_CONSUMER_KEY: str = "${MPESA_CONSUMER_KEY}"
MPESA_CONSUMER_SECRET: str = "${MPESA_CONSUMER_SECRET}"
MPESA_PASSKEY: str = "${MPESA_PASSKEY}"
MPESA_SHORTCODE: str = "${MPESA_SHORTCODE}"
MPESA_ENV: str = "sandbox"
```

### Usage

```python
from swx_core.services.billing.provider_factory import get_local_payment_provider

provider = get_local_payment_provider("paystack")
result = await provider.initialize_payment(
    amount=5000, currency="NGN", email="user@example.com",
    reference="tx_001", callback_url="https://app.example.com/callback"
)
# → {"provider": "paystack", "reference": "tx_001", "authorization_url": "https://...", ...}

verification = await provider.verify_payment("tx_001")
# → {"provider": "paystack", "reference": "tx_001", "status": "success", "paid": True, ...}
```

### Provider Comparison

| Feature | Paystack | Flutterwave | M-Pesa |
|---------|----------|-------------|--------|
| Countries | NG, GH | NG, KE, ZA, GH | KE |
| Initialize | ✅ | ✅ | ✅ (STK Push) |
| Verify | ✅ | ✅ | ✅ |
| Refund | ✅ | ✅ | ❌ |
| Auth | Bearer token | Bearer token | OAuth2 + password |

---

## API Endpoints

### Admin (`/api/admin/billing`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/currencies` | Create a currency |
| GET | `/currencies` | List currencies (`?active_only=true`) |
| GET | `/currencies/{code}` | Get currency by code |
| PUT | `/currencies/{code}` | Update currency |
| POST | `/exchange-rates` | Set manual exchange rate |
| GET | `/exchange-rates/{base}` | Get all rates for a base currency |
| POST | `/exchange-rates/sync` | Sync rates from source (`?base=USD`) |
| GET | `/tax/{jurisdiction}` | Get tax rate for a country code |
| GET | `/tax` | List all supported jurisdictions |

### User (`/api/user/billing`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/wallets` | List current user's wallets |
| GET | `/wallets/{currency}/balance` | Get or create wallet balance |
| POST | `/wallets/{currency}/credit` | Credit wallet (nano-units) |
| POST | `/convert` | Convert between currencies |
| POST | `/payments/initialize` | Initialize payment via provider |
| POST | `/payments/verify` | Verify payment status |

---

## Default Currencies

| Code | Name | Base | Providers |
|------|------|------|-----------|
| USD | US Dollar | ✅ | paystack, flutterwave |
| NGN | Nigerian Naira | | paystack, flutterwave |
| KES | Kenyan Shilling | | flutterwave, mpesa |
| ZAR | South African Rand | | paystack, flutterwave |
| GHS | Ghanaian Cedi | | paystack, flutterwave |

---

## File Structure

```
swx_core/
├── models/
│   └── currency.py                    # Currency, ExchangeRate, Wallet models + schemas + defaults
├── repositories/
│   ├── currency_repository.py         # CRUD for currencies
│   ├── exchange_rate_repository.py    # Rate storage and lookup
│   └── wallet_repository.py           # Wallet CRUD and balance updates
├── services/billing/
│   ├── exchange_rate_service.py       # 3-tier rate resolution + conversion
│   ├── tax_service.py                 # Country-specific tax calculation
│   ├── wallet_service.py              # Wallet ops + ledger integration + events
│   ├── provider_factory.py            # Provider selection + credential resolution
│   └── providers/
│       ├── __init__.py                # LocalPaymentProvider ABC
│       ├── paystack_provider.py       # Paystack integration
│       ├── flutterwave_provider.py    # Flutterwave integration
│       └── mpesa_provider.py          # M-Pesa STK Push integration
├── controllers/
│   └── billing_controller.py          # Thin delegation layer
├── routes/
│   ├── admin/billing_currency_route.py # Admin: currencies, rates, tax
│   └── user/billing_route.py           # User: wallets, conversion, payments
└── template/project/migrations/versions/
    └── b7e1c2d3f4a5_add_multi_currency_tables.py
```

---

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `LOCAL_CURRENCY_ENABLED` | `True` | Enable/disable multi-currency feature |
| `DEFAULT_BASE_CURRENCY` | `"USD"` | Fallback base currency for pivot resolution |
| `PAYSTACK_SECRET_KEY` | `"${PAYSTACK_SECRET_KEY}"` | Paystack secret (env placeholder) |
| `PAYSTACK_PUBLIC_KEY` | `"${PAYSTACK_PUBLIC_KEY}"` | Paystack public key |
| `FLUTTERWAVE_SECRET_KEY` | `"${FLUTTERWAVE_SECRET_KEY}"` | Flutterwave secret |
| `FLUTTERWAVE_PUBLIC_KEY` | `"${FLUTTERWAVE_PUBLIC_KEY}"` | Flutterwave public key |
| `FLUTTERWAVE_ENCRYPTION_KEY` | `"${FLUTTERWAVE_ENCRYPTION_KEY}"` | Flutterwave encryption key |
| `MPESA_CONSUMER_KEY` | `"${MPESA_CONSUMER_KEY}"` | M-Pesa consumer key |
| `MPESA_CONSUMER_SECRET` | `"${MPESA_CONSUMER_SECRET}"` | M-Pesa consumer secret |
| `MPESA_PASSKEY` | `"${MPESA_PASSKEY}"` | M-Pesa passkey |
| `MPESA_SHORTCODE` | `"${MPESA_SHORTCODE}"` | M-Pesa business shortcode |
| `MPESA_ENV` | `"sandbox"` | M-Pesa environment (`sandbox` or `production`) |
