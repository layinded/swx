# Migration Guide: v2.7.41 → v2.7.42

## Critical Stripe Billing Fixes

This release fixes 4 production-breaking bugs in the Stripe billing module.

### Migration Required: Plan Model Schema Changes

The `Plan` model now includes Stripe-specific columns that must be added to your database:

```sql
ALTER TABLE swx_billing_plan
    ADD COLUMN stripe_price_id VARCHAR(255),
    ADD COLUMN stripe_product_id VARCHAR(255),
    ADD COLUMN amount INTEGER,
    ADD COLUMN currency VARCHAR(3) DEFAULT 'usd';

CREATE INDEX ix_billing_plan_stripe_price_id ON swx_billing_plan (stripe_price_id);
```

#### Alembic Migration Template

```python
"""add_stripe_fields_to_billing_plan

Revision ID: YOUR_REVISION_ID
Revises: PREVIOUS_REVISION_ID
Create Date: 2026-07-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'YOUR_REVISION_ID'
down_revision = 'PREVIOUS_REVISION_ID'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('swx_billing_plan', sa.Column('stripe_price_id', sa.String(length=255), nullable=True))
    op.add_column('swx_billing_plan', sa.Column('stripe_product_id', sa.String(length=255), nullable=True))
    op.add_column('swx_billing_plan', sa.Column('amount', sa.Integer(), nullable=True))
    op.add_column('swx_billing_plan', sa.Column('currency', sa.String(length=3), server_default='usd', nullable=True))
    op.create_index('ix_billing_plan_stripe_price_id', 'swx_billing_plan', ['stripe_price_id'])


def downgrade() -> None:
    op.drop_index('ix_billing_plan_stripe_price_id', table_name='swx_billing_plan')
    op.drop_column('swx_billing_plan', 'currency')
    op.drop_column('swx_billing_plan', 'amount')
    op.drop_column('swx_billing_plan', 'stripe_product_id')
    op.drop_column('swx_billing_plan', 'stripe_price_id')
```

### Seeding Stripe Price IDs

After running the migration, populate the `stripe_price_id` for each plan:

```sql
UPDATE swx_billing_plan SET stripe_price_id = 'price_YOUR_STRIPE_PRICE_ID', stripe_product_id = 'prod_YOUR_STRIPE_PRODUCT_ID', amount = 2000, currency = 'usd' WHERE key = 'pro_v1';
UPDATE swx_billing_plan SET stripe_price_id = 'price_YOUR_STRIPE_PRICE_ID', stripe_product_id = 'prod_YOUR_STRIPE_PRODUCT_ID', amount = 4900, currency = 'usd' WHERE key = 'team_v1';
-- Repeat for each plan...
```

### Interface Changes

The `BillingProvider.create_checkout_session()` parameter was renamed from `plan_id` to `price_id`. If you have custom billing providers, update the signature:

```python
# BEFORE
async def create_checkout_session(self, customer_id: str, plan_id: str, ...) -> str:

# AFTER
async def create_checkout_session(self, customer_id: str, price_id: str, ...) -> str:
```

### New Methods

The `BillingProvider` interface now requires these additional methods:

- `create_portal_session(customer_id, return_url)` → Returns portal URL
- `create_subscription(customer_id, price_id, metadata)` → Creates direct subscription
- `get_subscription(subscription_id)` → Retrieves subscription details
- `get_customer(customer_id)` → Retrieves customer details

### Verification Steps

After upgrading to v2.7.42:

1. **Run migration**: `alembic upgrade head`
2. **Seed Stripe price IDs**: Update each plan with its corresponding Stripe price/product IDs
3. **Test checkout**: POST `/api/v1/billing/checkout` with a valid plan_key
4. **Test portal**: POST `/api/v1/billing/portal` should return a valid Stripe portal URL
5. **Test webhooks**: Send a `checkout.session.completed` event from Stripe CLI

### Breaking Changes

- `create_checkout_session` parameter renamed: `plan_id` → `price_id`
- New required methods on `BillingProvider`: `create_portal_session`, `create_subscription`, `get_subscription`, `get_customer`
- Plan model has 4 new columns (all nullable): `stripe_price_id`, `stripe_product_id`, `amount`, `currency`