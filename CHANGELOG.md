# Changelog

All notable changes to this project will be documented in this file.

## [2.19.16] - 2026-08-11

### Fixed — Entitlement resolver: scalar_one_or_none() crash on multi-row query, redundant DB queries, unused imports

`get_remaining_quota()` called `scalar_one_or_none()` on a query that can return
multiple `UsageRecord` rows (one per feature per billing period). When more than
one record existed, SQLAlchemy raised `MultipleResultsFound`. Replaced with
`func.coalesce(func.sum(UsageRecord.quantity), 0)` to aggregate correctly.

Additional improvements during code-clarity review:

| Change | Detail |
|---|---|
| Extracted `_get_account_and_subscription()` | Eliminates duplicated 20-line account+subscription query block that appeared in both `get_entitlement()` and `get_remaining_quota()` |
| Eliminated redundant DB queries in `get_remaining_quota()` | Previously called `get_entitlement()` which re-queried account+subscription (6 extra queries). Now inlines the entitlement lookup, reducing queries from 9 to 3 |
| Replaced magic number `999999999` | Named constant `UNLIMITED_QUOTA = 999_999_999` |
| Extracted `_ACTIVE_STATUSES` frozenset | `[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]` was duplicated; now a module-level constant |
| Removed unused imports | `Union`, `Dict`, `Any`, `Plan` were imported but never used |
| f-string → lazy logging | `logger.warning(f"...")` → `logger.warning("...", feature_key)` |

---

## [2.19.15] - 2026-08-11

### Fixed — Defensive session.add() for model mutations in hooks, invitations, settings, onboarding

The `create_personal_team` hook set `user.tenant_id = team.id` without calling
`session.add(user)`, so SQLAlchemy didn't track the change and `tenant_id` stayed
NULL in the database. This was the root-cause bug reported.

Audit of the same pattern across the codebase found three more files with the same
risk — model objects mutated after a `session.commit()` or `session.flush()` without
explicit `session.add()` to re-register them as dirty:

| File | Mutation | Fix |
|---|---|---|
| `swx_core/core/default_hooks.py` | `user.tenant_id = team.id` | Added `session.add(user)` after line 125 |
| `swx_core/services/team_invitation_service.py` | 5 status transitions | Added `self.session.add(invitation)` after each mutation |
| `swx_core/services/settings_crud_service.py` | Config value/description/active updates | Added `session.add(config)` before `session.add(history)` |
| `swx_core/repositories/onboarding_repository.py` | `complete_step` and `skip_step` | Added `session.add(step)` before `session.commit()` |

---

## [2.19.14] - 2026-08-11

### Fixed — tenant_id not persisted after create_personal_team hook

`create_personal_team` in `default_hooks.py` set `user.tenant_id = team.id` on the
Python object but didn't call `session.add(user)`. SQLAlchemy doesn't track mutations
on objects that have been expunged from the session or aren't marked dirty, so
`tenant_id` stayed NULL in the database even though the team was created successfully.

Added `session.add(user)` after the mutation so SQLAlchemy includes the UPDATE in
the current transaction's flush.

| File | Change |
|---|---|
| `swx_core/core/default_hooks.py` | Added `session.add(user)` after `user.tenant_id = team.id` |

---

## [2.19.13] - 2026-08-11

### Fixed — Alembic config path not passed to subprocess calls

All Alembic subprocess invocations (`alembic upgrade head`, `alembic downgrade`, `alembic revision`) across the codebase called the `alembic` CLI without specifying a config path. In container environments where `alembic.ini` is not in the CWD (e.g. `/app/migrations/alembic.ini`), this produces `No 'script_location' key found in configuration`, causing:

- `db_setup.run_alembic_migrations()` fails silently — migrations never run
- Superuser seeding is skipped (it runs after migrations)
- `swx db migrate`, `swx db downgrade`, `swx db revision` all fail in containers
- `swx setup` and `swx upgrade` silently skip migrations

Added `ALEMBIC_CONFIG_PATH` setting (default: `"alembic.ini"`) and passed `-c <path>` to every `alembic` subprocess call.

| File | Change |
|---|---|
| `swx_core/config/settings.py` | Added `ALEMBIC_CONFIG_PATH` setting (default `"alembic.ini"`) |
| `swx_core/database/db_setup.py` | Added `_alembic_cmd()` helper; `run_alembic_migrations()` now passes `-c` |
| `swx_core/cli/commands/db.py` | Added `_alembic_cmd()` helper; all 3 commands pass `-c` |
| `swx_core/cli/commands/framework.py` | `_setup_database()` and `upgrade()` now pass `-c` |
| `swx_core/cli/commands/make.py` | `migration()` and scaffold migration now pass `-c` |

**Container deployment**: Set `ALEMBIC_CONFIG_PATH=/app/alembic.ini` in your `.env` or environment.

---

## [2.19.12] - 2026-08-11

### Fixed — Circular FK (swx_users ↔ swx_team) and broken JSONB server_default

**Circular FK:** `swx_users.tenant_id` referenced `swx_team.id` via ForeignKey, while `swx_team.owner_id` referenced `swx_users.id`. This circular dependency prevented `metadata.create_all()` from creating either table — both FKs are unsatisfiable during DDL because neither table exists yet.

The fix removes the ForeignKey from `UserBase.tenant_id` while keeping the column as an indexed UUID. The relationship is already enforced at the application level via `create_personal_team`, and `swx_team.owner_id → swx_users.id` remains intact as the authoritative FK direction.

**Broken JSONB default:** `ApiKeyScopeBase.metadata_` and `ApiKeyScopeBase.is_active` had bare-string `server_default` values (`"'{}'::jsonb"` and `"true"`). SQLAlchemy treats plain-string server_defaults as literals to be SQL-quoted, producing triple-quoted output (`'''{}''::jsonb'`) that PostgreSQL rejects for JSONB columns. Fixed by wrapping with `text()`: `server_default=text("'{}'::jsonb")` and `server_default=text("true")`, which tells SQLAlchemy these are SQL expressions, not literal strings.

| File | Change |
|---|---|
| `swx_core/models/user.py` | Removed `ForeignKey("swx_team.id", ondelete="SET NULL")` from `tenant_id`; removed unused `ForeignKey` import |
| `swx_core/models/api_key_scope.py` | Changed `server_default="'{}'::jsonb"` → `text("'{}'::jsonb")` and `server_default="true"` → `text("true")`; added `text` import |

---

## [2.19.11] - 2026-08-11

### Fixed — Template migration also had swx_user (singular) FK reference

The project scaffold template `e8c1f3d5a9b2_add_onboarding_step_table.py` used
`ForeignKeyConstraint(["user_id"], ["swx_user.id"])` (singular) instead of
`["swx_users.id"]` (plural). This caused `NoReferencedTableError` for projects
generated via `swx new` that then ran `metadata.create_all()`.

Also confirmed via full FK audit: all 62 ForeignKey references in swx_core/models/
are correct (use `swx_users` plural). No other singular/plural mismatches exist.

| File | Change |
|---|---|
| `swx_core/template/project/migrations/versions/e8c1f3d5a9b2_add_onboarding_step_table.py` | `["swx_user.id"]` → `["swx_users.id"]` |

---

## [2.19.10] - 2026-08-11

### Fixed — FK table name mismatch: `swx_onboarding_step.user_id` referenced `swx_user.id` (singular) instead of `swx_users.id` (plural)

`OnboardingStep.user_id` declared `ForeignKey('swx_user.id')` but the User model's
`__tablename__` is `swx_users` (plural). This caused SQLAlchemy's
`metadata.create_all()` to raise `NoReferencedTableError`, blocking 32 of 66
SWX tables from being created (including `swx_team`, `swx_organization`,
`swx_conversation`, `swx_llm_provider_config`, `swx_notification`, and 28 others).

The same incorrect reference existed in the Alembic migration
`v2_19_0_add_onboarding_step.py`.

| File | Change |
|---|---|
| `swx_core/models/onboarding.py` | `ForeignKey("swx_user.id")` → `ForeignKey("swx_users.id")` |
| `swx_core/database/migrations/v2_19_0_add_onboarding_step.py` | `sa.ForeignKey("swx_user.id")` → `sa.ForeignKey("swx_users.id")` |

---

## [2.19.9] - 2026-08-10

### Fixed — Post-register hooks used separate sessions, causing silent failures (create_personal_team never ran)

All three default post-register hooks (`assign_default_role`, `create_billing_account`, `create_personal_team`) opened their own `AsyncSessionLocal()` session instead of using the parent registration session. This caused two bugs:

1. **Lazy-load / MissingGreenlet errors** — Hooks accessed `user.full_name`, `user.email`, etc. on the parent session's `user` object from within a separate session context, triggering `DetachedInstanceError` or `MissingGreenlet` exceptions that were silently swallowed by the `combined_post_hook` wrapper.
2. **Non-atomic registration** — If a hook failed, the user was still created but without a team/role/billing account (half-baked user).

The fix changes the `PostRegisterHook` signature from `(user, context)` to `(user, session, context)`. Hooks now receive the parent `AsyncSession` and share the same transaction. If any hook fails, the entire registration rolls back — no more half-baked users.

**Breaking change for custom post-register hooks:** Any custom hooks registered via `add_post_register()` must add an `AsyncSession` parameter as the second argument:

```python
# Before (v2.19.8 and earlier)
async def my_hook(user: User, context: dict) -> User: ...

# After (v2.19.9+)
async def my_hook(user: User, session: AsyncSession, context: dict) -> User: ...
```

Also removes the redundant bulk `UPDATE` in `create_personal_team` (setting `tenant_id` via `update(UserModel)` in a separate session). Now that the hook uses the parent session, `user.tenant_id = team.id` is sufficient — it persists on the caller's commit.

| File | Change |
|---|---|
| `swx_core/core/hooks.py` | `PostRegisterHook` type now includes `AsyncSession` parameter; `combined_post_hook` forwards session |
| `swx_core/core/default_hooks.py` | All three hooks rewritten to use parent session; removed `AsyncSessionLocal()` and `session.commit()` calls; `create_personal_team` no longer uses bulk `UPDATE` |
| `swx_core/services/auth_service.py` | `post_register_hook` signature updated; call site now passes `session` |
| `docs/04-core-concepts/REGISTRATION_HOOKS.md` | Updated all examples to new `(user, session, context)` signature |

---

## [2.19.8] - 2026-08-07

### Fixed — OAuth registration bypasses default hooks (role assignment, billing account, personal team)

All three OAuth callback handlers (`google_auth_callback`, `facebook_auth_callback`, `provider_auth_callback`) in `oauth_route.py` called `register_user_service()` directly without passing `pre_register_hook` and `post_register_hook`. This meant users registered via social login never ran the default registration hooks registered by `_register_default_hooks()` in `bootstrap.py`:

- `create_personal_team` — no personal team created
- `assign_default_role` — no default role assigned
- `create_billing_account` — no billing account created

Meanwhile, email registration via `register_controller` correctly wired these hooks. The fix adds `registration_hooks.pre_register` and `registration_hooks.post_register` to all three OAuth call sites, ensuring consistent behavior across all registration paths.

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Added `from swx_core.core.hooks import registration_hooks`; passed `pre_register_hook` and `post_register_hook` in all three OAuth callbacks |

---

## [2.19.7] - 2026-08-04

### Fixed — `sync_stripe_subscription` duplicate active subscriptions, checkout-session no-op, 10 edge-case bugs

#### P0 — `sync_stripe_subscription` creates duplicate ACTIVE subscriptions (from bug report)

`sync_stripe_subscription` inserted a new `Subscription` row when a Stripe webhook fired for a subscription with no local match (by `stripe_subscription_id`). It did **not** deactivate existing active subscriptions for the same billing account before inserting, producing multiple `ACTIVE` rows. This crashed `GET /billing/subscription` because `BillingController.get_subscription` uses `scalar_one_or_none()` → `MultipleResultsFound`.

The sibling method `create_subscription` already implemented the correct deactivation pattern. `sync_stripe_subscription` now does the same before insert, using a shared `_deactivate_active_subscriptions()` helper.

| File | Change |
|---|---|
| `swx_core/services/billing/subscription_service.py` | Added `_deactivate_active_subscriptions()` helper; called before insert in `sync_stripe_subscription` and `create_subscription` |

---

#### P1 — `checkout.session.completed` webhook sync was a silent no-op

The webhook handler called `sync_stripe_subscription(event_data)` for `checkout.session.completed` events. A Stripe Checkout Session object does **not** contain `current_period_start` or `current_period_end` fields — those exist only on the Subscription object. The method silently returned without syncing anything, while the handler reported "subscription synchronized" to Stripe.

**Fix:** When period fields are missing but a `subscription` field (string ID) is present, `_sync_from_checkout_session()` fetches the full subscription object from Stripe via the provider and retries the sync. Recursion depth guard prevents infinite loops.

| File | Change |
|---|---|
| `swx_core/services/billing/subscription_service.py` | Added `_sync_from_checkout_session()` method with recursion depth guard |

---

#### Edge cases fixed (12 total)

| # | Severity | Edge Case | Fix |
|---|---|---|---|
| 1 | High | Update branch missing `ended_at` when status becomes CANCELED | Set `ended_at` on cancellation in update branch |
| 2 | High | Insert branch creates ghost CANCELED/EXPIRED rows for never-synced subs | Skip insert when `status in TERMINAL_STATUSES` |
| 3 | High | Update branch missing `canceled_at` when `cancel_at_period_end=True` | Set `canceled_at` on `cancel_at_period_end` in update branch |
| 4 | Medium | `_sync_from_checkout_session` unguarded recursion | Added `depth` parameter, abort at `depth >= 2` |
| 5 | High | `_deactivate_active_subscriptions` didn't cancel `PAST_DUE` subs (entitlement resolver treats PAST_DUE as active) | Added `PAST_DUE` to `ACTIVE_STATUSES` canonical constant |
| 6 | High | Deactivation event fired before commit — listeners saw uncommitted data | Helper returns canceled IDs; callers emit event after commit |
| 7 | High | `create_subscription` event ordering — deactivation event before creation event, both before commit | Deactivation event now fires after commit, before creation event |
| 8 | Medium | Update branch overwrote `ended_at` on every CANCELED webhook resend | Only set `ended_at` if `subscription.ended_at is None` |
| 9 | Low | `_from_stripe_timestamp` accepted `bool` (bool is subclass of int) | Added `_is_numeric_timestamp()` TypeGuard, excludes bool |
| 10 | Medium | `cancel_subscription` not idempotent — double-call emitted duplicate events | Added `already_canceled` check, skip if already canceled at period end |
| 11 | Medium | Insert branch missing `canceled_at` when `cancel_at_period_end=True` | Added `canceled_at` to insert constructor |
| 12 | Medium | `_get_stripe_price_id` returned Plan ID from legacy `plan` field, not Price ID | Removed legacy `plan` field path; only `items.data[0].price.id` used |

---

#### Code clarity

| Change |
|---|
| Extracted `_commit_or_rollback()` helper — 5 duplicate try/commit/except/rollback blocks eliminated |
| Extracted `_update_existing_subscription()` and `_create_subscription_from_stripe()` from `sync_stripe_subscription` |
| `sync_stripe_subscription` reduced from 120 lines to 41 lines (pure orchestration) |
| Extracted `_is_numeric_timestamp()` with `TypeGuard[int | float]` for type-safe timestamp validation |
| Added `ACTIVE_STATUSES` and `TERMINAL_STATUSES` canonical constants to `billing.py` |
| `billing_repository.py` now imports canonical `ACTIVE_STATUSES` instead of private `_ACTIVE_STATUSES` |

---

#### Events added

`subscription_service.py` previously emitted **zero** events. Now emits:

| Method | Event | Payload |
|---|---|---|
| `_deactivate_active_subscriptions` (via callers) | `subscription.deactivated` | `account_id`, `canceled_subscription_ids[]` |
| `create_subscription` | `subscription.created` | `subscription_id`, `account_id`, `plan_key`, `status` |
| `cancel_subscription` | `subscription.canceled` | `subscription_id`, `immediate`, `cancel_at_period_end` |
| `sync_stripe_subscription` (update) | `subscription.updated` | `subscription_id`, `stripe_subscription_id`, `status`, `source` |
| `sync_stripe_subscription` (insert) | `subscription.created` | `subscription_id`, `account_id`, `stripe_subscription_id`, `status`, `source` |

All events fire **after** successful commit, never before.

---

### Changed

| File | Change |
|---|---|
| `swx_core/models/billing.py` | Added `ACTIVE_STATUSES`, `TERMINAL_STATUSES` constants, `__all__` export list |
| `swx_core/repositories/billing_repository.py` | Replaced private `_ACTIVE_STATUSES` with canonical import |
| `swx_core/services/billing/subscription_service.py` | All fixes, edge cases, events, code clarity |

---

## [2.19.5] - 2026-08-04

### Fixed — MissingGreenlet crash on registration, dead code removal, lazy-loading fixes

#### P0 — `MissingGreenlet` crash on `/api/auth/register` (from v2.19.4)

`create_personal_team` hook updates `User.tenant_id` via a bulk `UPDATE` statement in a separate session, triggering `onupdate=func.now()` on `updated_at` in the DB. The in-memory `user` object never picks up the new `updated_at` value, so FastAPI's response serialization triggers a lazy-load on `AsyncSession` → `MissingGreenlet` → 500.

**Fix:** Added `await session.refresh(user)` after post-register hooks in `auth_service.py` to reload all DB-generated columns.

| File | Change |
|---|---|
| `swx_core/services/auth_service.py` | Added `await session.refresh(user)` after hook block |

---

#### P1 — Silent exception swallowing in `auto_accept_invitation` hook

`except (ValueError, Exception): pass` catches **all** exceptions (including programming errors) and silently discards them. `ValueError` from invalid UUID format is expected; other exceptions should be logged.

**Fix:** Split into `except ValueError:` (logged warning) and `except Exception:` (logged with traceback).

| File | Change |
|---|---|
| `swx_core/hooks/invitation_auto_accept.py` | Split bare `except` into typed handlers with logging |

---

#### P2 — `Relationship()` without `lazy=` causes `MissingGreenlet` on attribute access

Three model fields used bare `Relationship()` which defaults to `lazy="select"` (lazy loading). On `AsyncSession`, accessing these attributes outside the session context crashes with `MissingGreenlet`.

**Fix:** Added `lazy="selectin"` to eagerly load these relationships within the same query.

| File | Change |
|---|---|
| `swx_core/models/device.py` | `user: "User" = Relationship()` → `Relationship(lazy="selectin")` |
| `swx_core/models/team_member.py` | `user` and `team_role` → `Relationship(lazy="selectin")` |

---

#### Removed — Dead code

| File | Change |
|---|---|
| `swx_core/repositories/token_repository.py` | Deleted — not imported anywhere, superseded by `refresh_token_service.py` |

---

## [2.19.4] - 2026-08-04

### Fixed — MissingGreenlet crash on registration (hotfix)

#### P0 — `create_personal_team` post-register hook crashes with `MissingGreenlet`

Same root cause as v2.19.5 P0 but without the `session.refresh()` fix. This version was superseded by v2.19.5 within minutes.

---

## [2.19.3] - 2026-08-04

### Fixed — `session.exec()` on AsyncSession (6 instances), CSRF token length, code-clarity

#### P0 — `session.exec()` on `AsyncSession` — crashes every call site

`AsyncSession` has no `.exec()` method (that's SQLModel's `Session`). Six call sites used it, causing `AttributeError` at runtime.

| File | Change |
|---|---|
| `swx_core/core/default_hooks.py` | `await session.exec()` → `await session.execute()` |
| `swx_core/services/team_permission_checker.py` | 4× `await self.session.exec()` → `await self.session.execute()` |
| `swx_core/security/dependencies.py` | `session.exec()` → `(await session.execute()).scalars().first()` |

#### P1 — `get_current_user` was sync but uses `AsyncSession`

`get_current_user` in `security/dependencies.py` was a sync function receiving `AsyncSession` via `SessionDep`. Calling `.execute()` on `AsyncSession` requires `await`. Made the function `async`.

| File | Change |
|---|---|
| `swx_core/security/dependencies.py` | `def get_current_user` → `async def get_current_user` |

#### P2 — CSRF token generation produces 10,800-byte tokens

`_get_or_create_csrf_token()` used `config.cookie_max_age // 8` (= 10,800) as the token byte length instead of `CSRF_TOKEN_LENGTH` (= 32).

| File | Change |
|---|---|
| `swx_core/middleware/csrf_middleware.py` | `secrets.token_urlsafe(config.cookie_max_age // 8)` → `secrets.token_urlsafe(CSRF_TOKEN_LENGTH)` |

#### Code-clarity

| File | Change |
|---|---|
| `swx_core/security/dependencies.py` | Merged duplicate docstrings, removed redundant comment |
| `swx_core/version.py` | Removed unused `Optional` import, fixed bare `tuple` → `tuple[int, ...]` |

---

## [2.19.2] - 2026-08-03

### Fixed — CSRF token length bug (hotfix)

`_get_or_create_csrf_token()` used `cookie_max_age // 8` (10,800 bytes) instead of `CSRF_TOKEN_LENGTH` (32 bytes). Same fix as v2.19.3 P2, released separately for urgency.

---

## [2.19.1] - 2026-08-03

### Fixed — Backward-compatibility breaks from v2.19.0

#### P0 — `ImportError: cannot import name 'async_session'` kills audit subsystem

`audit_event_queue.py` and `security.py` imported `async_session` from `swx_core.database.db`, but the symbol was removed in v2.19.0. Added backward-compat alias.

| File | Change |
|---|---|
| `swx_core/database/db.py` | Added `async_session = AsyncSessionLocal` alias |
| `swx_core/database/__init__.py` | Added `async_session` to exports |

#### P1 — `ImportError: cannot import name 'CSRF_HEADER_NAME'`

`CSRF_HEADER_NAME`, `CSRF_TOKEN_LENGTH`, and `CSRF_COOKIE_NAME` were module-level constants removed in v2.19.0's CSRF rewrite. Restored for backward compatibility.

| File | Change |
|---|---|
| `swx_core/middleware/csrf_middleware.py` | Restored `CSRF_HEADER_NAME`, `CSRF_TOKEN_LENGTH`, `CSRF_COOKIE_NAME` as module-level constants |

#### P2 — Stale `__version__` attribute (2.17.0 instead of 2.19.0)

`swx_core/version.py` had `VERSION_MINOR = 17, VERSION_PATCH = 0` while `pyproject.toml` said `2.19.0`.

| File | Change |
|---|---|
| `swx_core/version.py` | Updated version to match `pyproject.toml` |

#### P3 — `stream_controller` return type mismatch

`llm_controller.stream_controller` had `AsyncGenerator[str, None]` but `llm_service.stream()` yields `SSEEvent`.

| File | Change |
|---|---|
| `swx_core/controllers/llm_controller.py` | Fixed return type to `AsyncGenerator[SSEEvent, None]`, renamed `chunk` → `event` |

---

## [2.19.0] - 2026-08-03

### Added — 40 upstream implementation tickets

(See UPSTREAM_IMPLEMENTATION_PLAN.md for full details.)

New modules: fallback chain, region routing, auth rate limiting, onboarding, provider catalog, cache service, tenant config cache, audit retention, audit event queue, compliance report, prompt injection, encryption, security headers, CSRF, service token guard, combined auth guard, lazy import, error hierarchy.

---

## [2.18.0] - 2026-07-30

### Added — System Config Value Type: FLOAT + Wrapped-Scalar Unwrapping

Extends `SettingValueType` with `FLOAT` and alias values (`INTEGER`, `BOOLEAN`), and updates `SettingsService._convert_value()` to unwrap single-key dict values for scalar types. Unblocks FastPII production seeding.

---

#### New: `FLOAT` value type + `INTEGER`/`BOOLEAN` aliases

The `SettingValueType` enum and the PostgreSQL `settingvaluetype` enum now include `float`, `integer`, and `boolean`. `INTEGER` and `BOOLEAN` are semantic aliases for `INT` and `BOOL`.

| File | Change |
|---|---|
| `swx_core/models/system_config.py` | Added `FLOAT`, `INTEGER`, `BOOLEAN` to `SettingValueType` |
| `swx_core/database/migrations/v2_18_0_add_setting_value_type_float.py` | New migration: `ALTER TYPE settingvaluetype ADD VALUE` for `float`, `integer`, `boolean` |

---

#### New: `SettingsService.get_float()`

```python
threshold = await service.get_float("detection.confidence_threshold", default=0.7)
```

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Added `get_float()` method |

---

#### Fixed: `_convert_value()` unwraps single-key dicts for scalar types

FastPII wraps scalar config values in single-key JSON objects (e.g. `{"threshold": 0.7}`). Previously, `int({"max_length": 50000})` silently returned `0`, causing detection requests to fail. Now `_unwrap_scalar()` extracts the inner value before conversion.

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Added `_unwrap_scalar()` helper + `_SCALAR_VALUE_TYPES`; updated `_convert_value()` to unwrap and handle `FLOAT`/aliases |
| `swx_core/services/settings_crud_service.py` | Updated `validate_setting_value()` to handle `FLOAT` and `INTEGER`/`BOOLEAN` aliases |

---

### Migration Required

Copy `swx_core/database/migrations/v2_18_0_add_setting_value_type_float.py` to your project's `migrations/versions/` directory, set `down_revision`, and run `alembic upgrade head`. See `MIGRATION_GUIDE_v2.18.0.md` for details.

### Backward Compatibility

- All existing `INT`, `BOOL`, `STRING`, `JSON` configs work unchanged.
- Bare scalar values are not affected by the unwrapping logic.
- The migration `downgrade()` is a no-op — PostgreSQL cannot remove individual enum values.

---

## [2.17.0] - 2026-07-30

### Fixed — OAuth Multi-Domain Support & Registration Bug

3 fixes from FastPII Platform production deployment. Includes a P0 registration-breaking bug, a P1 multi-domain redirect issue, and a P2 configuration gap for multi-redirect-URI support.

---

#### P0 — OAuth registration fails: `secrets.token_urlsafe(32)` generates 43-char password exceeding `UserCreate.password` max_length of 40

When a new user registers via OAuth (Google, Facebook, or any custom provider), `secrets.token_urlsafe(32)` generates a 43-character string that exceeds `UserCreate.password`'s `max_length=40`, causing a Pydantic validation error. This blocks **all new OAuth user registrations**.

**Fix:** Changed all three OAuth callback handlers to use `secrets.token_urlsafe(28)` (~38 chars, within the 40-char limit).

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | `token_urlsafe(32)` → `token_urlsafe(28)` in Google, Facebook, and generic provider callbacks |

---

#### P1 — OAuth callback redirects to `FRONTEND_HOST` instead of preserving origin domain

OAuth callbacks were hardcoded to redirect to `FRONTEND_HOST` regardless of which subdomain the user started from. Users on `chat.fastpii.com` would be redirected to `fastpii.com` after login, losing their context.

**Fix:** Added origin preservation through the OAuth flow:
- `store_pkce_session()` captures `origin` from query params or `Referer` header, stores in session as `oauth_origin`
- `complete_oauth_login()` reads `oauth_origin` from session and redirects to the origin domain
- `clear_oauth_session()` cleans up `oauth_origin`

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Origin capture in `store_pkce_session()`, origin-based redirect in `complete_oauth_login()`, cleanup in `clear_oauth_session()` |

---

#### P2 — Single redirect URI limitation for multi-domain deployments

Only a single `GOOGLE_REDIRECT_URI` / `FACEBOOK_REDIRECT_URI` could be configured, forcing all OAuth flows through one domain. Multi-domain applications (chat.fastpii.com, app.fastpii.com, fastpii.com) needed separate redirect URIs registered with each OAuth provider.

**Fix:** Added multi-redirect-URI support with origin-based matching:

- `GOOGLE_REDIRECT_URIS` / `FACEBOOK_REDIRECT_URIS` — comma-separated list of allowed redirect URIs (takes precedence over single `*_REDIRECT_URI`)
- `{PROVIDER}_REDIRECT_URIS` — same for custom providers via `OAuthProviderSettings`
- `resolve_redirect_uri()` — matches request `Origin`/`Referer` header against allowed URIs, falls back to single configured URI

| File | Change |
|---|---|
| `swx_core/config/social_settings.py` | Added `GOOGLE_REDIRECT_URIS: list[str]` and `FACEBOOK_REDIRECT_URIS: list[str]` fields |
| `swx_core/core/oauth_providers.py` | Added `redirect_uris: list[str]` to `OAuthProviderConfig`, parses `{PROVIDER}_REDIRECT_URIS` from env |
| `swx_core/routes/access/oauth_route.py` | Added `resolve_redirect_uri()` helper; updated `google_login`, `facebook_login`, `provider_login` to use it |
| `.env.example` | Added `GOOGLE_REDIRECT_URIS` and `FACEBOOK_REDIRECT_URIS` examples |

---

#### P2 — OAuth URLs endpoint performance

`GET /api/oauth/urls` was rebuilding provider URLs on every request despite configuration being static.

**Fix:** Added `@lru_cache(maxsize=1)` to `_get_oauth_urls_cached()`.

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Wrapped URL builder in `lru_cache` |

---

### Configuration

| Setting | Default | Description |
|---|---|---|
| `GOOGLE_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for Google OAuth. Takes precedence over `GOOGLE_REDIRECT_URI`. |
| `FACEBOOK_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for Facebook OAuth. Takes precedence over `FACEBOOK_REDIRECT_URI`. |
| `{PROVIDER}_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for any custom OAuth provider. Takes precedence over `{PROVIDER}_REDIRECT_URI`. |

### Backward Compatibility

- **Fully backward compatible.** If `*_REDIRECT_URIS` is not set (empty list), the existing `*_REDIRECT_URI` single-URI behavior is used unchanged.
- Origin-based redirect matching only activates when the `Origin` or `Referer` header matches an allowed URI.
- The `secrets.token_urlsafe(28)` change only affects the placeholder password for OAuth registrations — regular email/password registrations are unaffected.

---

## [2.16.1] - 2026-07-29

### Added — NeuronaHealth Production Patterns

7 framework-level features adopted from NeuronaHealth's production deployment. All backward compatible.

---

#### #1 — Security Headers Middleware

New `swx_core/middleware/security_headers_middleware.py`. Adds X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, and HSTS (production only) to all responses.

```python
from swx_core.middleware.security_headers_middleware import setup_security_headers
setup_security_headers(app)
```

#### #2 — Device Registration Model

New `swx_core/models/device.py` for push notification token management. Platform enum (ios/android/web), FCM token, device metadata, status (active/inactive/unregistered), is_primary, last_used_at, extra_data (JSONB).

#### #3 — String-Based Rate Limit Parsing

New `parse_rate_limit("5/minute")` → `(5, 60)` and `enforce_rate_limit(request, limit="5/minute", namespace="auth:login")` in `enforce.py`. Human-readable rate strings for route handlers — no need to look up integer limits from the registry.

#### #4 — Trusted Proxy IP Extraction

New `get_client_ip(request)` in `enforce.py`. Handles X-Forwarded-For chains with `TRUSTED_PROXIES` validation — walks the chain backwards to find the first untrusted IP. Fixes rate limiting accuracy behind reverse proxies.

#### #5 — DB-Driven OTP Bypass with Per-Email Whitelist

`email_otp_service.py` now supports `OTP_BYPASS_EMAILS` setting (comma-separated whitelist). When `OTP_BYPASS_FOR_TESTING=True` and the email is in the whitelist (or whitelist is empty = all emails), OTP is bypassed. New `is_email_bypassed(email)` function. Also adds `OtpInvalidError`, `OtpRateLimitError`, `OtpDeliveryError` exception classes.

#### #6 — Redis-Backed Config Cache for Cross-Worker Invalidation

`SettingsService` now checks Redis before hitting the DB, and writes to Redis on DB miss. `invalidate_cache()` clears both in-process and Redis caches. Uses the container's `redis.client` singleton. Falls back to in-process-only when Redis is unavailable.

#### #7 — SystemConfig Defaults Registry

New `DEFAULT_SYSTEM_CONFIGS` list in `system_config.py` with 10 default config entries (auth token expiry, rate limit toggles, feature flags, job limits, audit retention, password policy, email toggle, maintenance mode). Services can reference these as fallback when DB has no entry.

---

### New Settings

| Setting | Default | Description |
|---|---|---|
| `OTP_BYPASS_EMAILS` | `""` | Comma-separated email whitelist for OTP bypass |
| `TRUSTED_PROXIES` | `""` | Comma-separated trusted proxy IPs for X-Forwarded-For parsing |

---

## [2.16.0] - 2026-07-29

### Added — Notification System Enhancements (Round 5 Feedback)

7 enhancements to the notification and email system, informed by NeuronaHealth's production deployment patterns. All changes are backward compatible.

---

#### #2 (P1) — Email Provider Cost/Limits/Country Routing

`EmailProviderConfig` now supports financial and operational control fields:

| Field | Type | Purpose |
|---|---|---|
| `cost_per_email` | `float \| None` | Cost tracking per send |
| `daily_limit` | `int \| None` | Max emails per day per provider |
| `monthly_limit` | `int \| None` | Max emails per month |
| `rate_limit_per_hour` | `int \| None` | Burst protection |
| `supported_countries` | `list[str]` | Country codes for regional routing (GDPR, data residency) |
| `tracking_enabled` | `bool` | Per-provider analytics control |
| `open_tracking` | `bool` | Track email opens |
| `click_tracking` | `bool` | Track link clicks |
| `reply_to` | `str \| None` | Reply-to address |

`provider_factory.py` adds:
- `get_email_provider_for_country(session, country)` — filters by `supported_countries`
- `send_via_email(session, notification, preferred_provider=...)` — force a specific provider

#### #1 (P2) — Hybrid Template Approach

`template_service.py` supports optional file-based base templates via `base_template_path` parameter. When provided, DB body content is rendered inside a file-based Jinja2 base layout using `{% extends %}` + `{% block content %}`. Uses `FileSystemLoader` from a configurable `NOTIFICATION_TEMPLATE_DIR` directory. Backward compatible — without `base_template_path`, the existing simple `Template(body).render(context)` path is used.

#### #3 (P2) — Email OTP Authentication Service

New `swx_core/services/auth/email_otp_service.py` with:
- `generate_otp(email)` — 6-digit OTP via `secrets.randbelow`, bcrypt-hashed
- `verify_otp(email, code)` — verifies against stored hash, tracks attempts
- `resend_otp(email)` — new OTP with cooldown enforcement
- Custom exception hierarchy: `OtpError` → `OtpInvalidError`, `OtpResendCooldownError`, `OtpRateLimitError`, `OtpDeliveryError`
- Configurable: `OTP_LENGTH`, `OTP_EXPIRY_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_BYPASS_FOR_TESTING`
- Bypass mode for testing environments

#### #4 (P2) — Notification Preference Escalation/Reminder Fields

`NotificationPreference` adds:
- `reminder_time: str | None` — preferred notification time (HH:MM)
- `escalation_enabled: bool` — retry undelivered critical notifications via alternate channel
- `escalation_hours: int | None` — hours before escalating

#### #5 (P2) — Celery Queue Integration

`send_notification()` accepts optional `queue: bool = False`. When `queue=True`, dispatches to a Celery task via `send_task()` instead of sending synchronously. Falls back to synchronous if Celery is not installed. Configurable task path via `NOTIFICATION_CELERY_TASK_PATH` setting.

#### #6 (P3) — Template Variable Enrichment

`render_template()` auto-injects brand defaults into every template context:
- `{{ brand_name }}` — from `NOTIFICATION_DEFAULT_FROM_NAME` or `PROJECT_NAME`
- `{{ brand_color }}` — from `NOTIFICATION_BRAND_COLOR`
- `{{ support_email }}` — from `NOTIFICATION_SUPPORT_EMAIL`
- `{{ frontend_url }}` — from `FRONTEND_HOST`

User context overrides defaults.

#### #7 (P3) — Provider Health Check and Statistics

`management_service.py` adds:
- `test_email_provider(session, provider_name)` — sends a test email, returns status
- `get_provider_statistics(session, days=30)` — aggregates delivery stats per provider

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/models/email_provider_config.py` | 9 new fields + schema updates |
| `swx_core/models/notification_preference.py` | 3 new fields + schema updates |
| `swx_core/services/notifications/provider_factory.py` | Country routing + preferred provider |
| `swx_core/services/notifications/template_service.py` | Hybrid templates + brand enrichment |
| `swx_core/services/notifications/notification_service.py` | Queue parameter + Celery dispatch |
| `swx_core/services/notifications/management_service.py` | Health check + statistics |
| `swx_core/services/auth/email_otp_service.py` | **New** — Email OTP service |
| `swx_core/services/notifications/tasks.py` | **New** — Celery task fallback |
| `swx_core/config/settings.py` | New notification/OTP settings |

---

## [2.15.6] - 2026-07-29

### Fixed — P0 Circular Import

**`import swx_core` crashed with `ImportError: cannot import name 'get_container'`** — the package was completely unusable.

The v2.15.0 timezone refactor added `from swx_core.utils.time import utc_now` to `repositories/base.py`, which triggered `swx_core/utils/__init__.py` for the first time in the container init chain. `utils/__init__.py` eagerly imports `utils.dependencies` which imports `get_container` from `container.container` at module level — creating a circular dependency since `container.container` was still being initialized.

**Fix:** Made `get_container` import lazy in `dependencies.py` — moved from module-level import to a `_get_container()` helper that imports inside the function body. All call sites updated to use `_get_container()`.

---

## [2.15.5] - 2026-07-29

### Fixed — Round 3 Feedback

5 issues from the FastPII Platform round 3 audit. Includes a P1 runtime crash fix, DEFAULT_PLAN_KEY consistency, rate limit dual-path prevention, and a centralized JSON utility.

---

#### P1 — Runtime Crash

- **`ledger_service.py` ImportError** — Dead import of `utc_now_naive` from `swx_core.models.ledger` (removed in v2.15.0 timezone refactor). Any code importing `ledger_service` would crash at import time. Replaced with `from swx_core.utils.time import utc_now`.

#### P1 — Incomplete Fixes

- **`plan_helper.py` hardcoded "free"** — 4 places returned `"free"` instead of `settings.DEFAULT_PLAN_KEY`. Rate limiting and entitlement checks for users without subscriptions ignored the configured default plan. All 4 replaced with `settings.DEFAULT_PLAN_KEY`.

- **Rate limit dual-path double counting** — `RateLimitMiddleware` now accepts `exempt_namespaces: list[str]` parameter. Routes matching these glob patterns skip middleware rate limiting, letting `enforce_limit()` handle them exclusively. Prevents double counting when both paths are used. Sets `request.state.rate_limit_handled = True` on exempt routes.

#### P3 — Minor

- **JWT billing_plan fallback** — Both `payload.get("billing_plan", "free")` calls in `rate_limit_middleware.py` replaced with `settings.DEFAULT_PLAN_KEY` for consistency.

#### P2 — Quality of Life

- **Centralized JSON utility** — New `swx_core/utils/json.py` with `SwxJSONEncoder` (UUID + datetime support), `dumps()`, and `loads()`. Available for incremental adoption across the codebase.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/ledger_service.py` | Replace dead `utc_now_naive` import with `utc_now` |
| `swx_core/services/billing/plan_helper.py` | Replace 4x `"free"` with `settings.DEFAULT_PLAN_KEY` |
| `swx_core/middleware/rate_limit_middleware.py` | Add `exempt_namespaces` param + 2x `"free"` → `settings.DEFAULT_PLAN_KEY` |
| `swx_core/utils/json.py` | **New** — centralized JSON encoder + dumps/loads |

---

## [2.15.4] - 2026-07-29

### Added — Dual-Format API Key Scopes + Code-Clarity Cleanup

`ApiKeyCreate.scopes` now accepts both `list[str]` (`["billing:read"]`) and `list[dict]` (`[{"resource": "billing", "action": "read"}]`) formats. Projects migrating from flat-string scope formats no longer need to change their API clients.

---

#### What Changed

- **`ApiKeyCreate.scopes`** — type changed from `list[dict[str, str]]` to `list[str] | list[dict[str, str]]`. Both formats are normalized internally to `swx_api_key_scope` rows.

- **`parse_scope_string()`** — new function in `api_key_scope_service.py`. Parses `"resource:action"` strings into `(resource, action)` tuples. Inverse of the existing `expand_scopes()`.

- **`_normalize_scopes()`** — new internal function in `api_key_service.py`. Normalizes mixed scope formats before persisting. Called automatically in `create_api_key()`.

- **Code-clarity cleanup** — removed redundant `_utc_now()` / `_utc_now_naive()` wrappers in `api_key_service.py`, `subscription_service.py`, and `job_runner.py` (all now call `utc_now()` directly). Removed dead imports across 4 files.

---

#### Backward Compatibility

- Existing clients sending `list[dict]` are unaffected
- New clients can send `list[str]` without any changes
- Storage format unchanged — still normalized rows in `swx_api_key_scope`
- Key generation and validation unchanged

---

## [2.15.3] - 2026-07-29

### Added — Per-Route Rate Limit API + Pluggable Config Resolver

Two new features that unblock projects with fine-grained rate limit namespaces and custom config tables.

---

#### #9 — Per-Route Rate Limit Enforcement API

New `enforce_limit()` function in `swx_core/services/rate_limit/enforce.py` allows route handlers to enforce rate limits with custom namespaces that cannot be inferred from the URL path alone.

```python
from swx_core.services.rate_limit.enforce import enforce_limit

@router.post("/detect/public")
async def detect_public(request: Request):
    await enforce_limit(request, namespace="detection:detect:public")
    ...
```

Resolves the actor from JWT/request.state, looks up the limit from the registry, checks Redis, and raises `HTTPException(429)` with standard rate limit headers if exceeded. Supports `custom_limit` parameter to bypass the registry entirely.

#### #7 — Pluggable SettingsService

`SettingsService.__init__()` now accepts an optional `model` parameter. Projects with their own config table can pass their custom SQLModel class instead of using the default `SystemConfig`:

```python
from swx_core.services.settings_service import SettingsService
from my_app.models import MyConfig

service = SettingsService(session, model=MyConfig)
```

The custom model must have `key` (str, unique), `value` (JSONB), `value_type` (SettingValueType), and `is_active` (bool) fields. This enables projects with existing config tables to use the framework's type-safe getters, TTL caching, and env fallback without a data migration.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/rate_limit/enforce.py` | **New** — `enforce_limit()` per-route API |
| `swx_core/services/settings_service.py` | Add `model` parameter to `__init__`, use `self.model` in `_get_from_db` |
| `docs/04-core-concepts/RATE_LIMITING.md` | Document `enforce_limit()` API with parameters table |
| `docs/04-core-concepts/SETTINGS.md` | Document custom config table usage |

---

## [2.15.2] - 2026-07-29

### Changed — SystemConfig JSONB + Metadata/Permissions JSONB

`SystemConfig.value` converted from `VARCHAR(5000)` to PostgreSQL `JSONB`. Metadata and permissions columns converted from generic `JSON` to `JSONB`. This enables GIN indexing, PostgreSQL JSON operators (`->`, `->>`, `@>`), and eliminates `json.loads()` on every DB read.

---

#### What Changed

- **`SystemConfig.value`** — changed from `VARCHAR(5000)` to `JSONB`. Values are now stored as native JSON types (strings, ints, bools, objects) and returned as native Python types via SQLAlchemy. No more `json.loads()` on DB reads. The `value_type` field is retained for env var fallback (where values are always strings) and validation.

- **`SystemConfig.metadata`** — changed from `JSON` to `JSONB` (both `SystemConfig` and `SystemConfigHistory` tables).

- **`SystemConfigHistory.old_value` / `new_value`** — changed from `VARCHAR(5000)` to `JSONB`.

- **`TeamRole.permissions`** — changed from `JSON` to `JSONB`.

- **`settings_service.py`** — `_convert_value()` updated to handle native JSONB types from DB (returns directly) AND string values from env vars (parses). `get_json()` simplified — DB values are already dicts from JSONB.

- **`settings_crud_service.py`** — `validate_setting_value()` and `validate_security_guards()` updated to handle native types (int, bool, dict) alongside string inputs.

- **Data migration** — `swx_core/database/migrations/v2_15_2_convert_system_config_jsonb.py` converts existing VARCHAR/JSON columns to JSONB using `USING ...::jsonb`.

---

#### Backward Compatibility

- Existing string values are automatically valid JSONB (a string is valid JSON)
- The data migration uses `USING column::jsonb` which handles existing VARCHAR data
- `value_type` field retained — env var fallback still needs type conversion
- API responses now return native types instead of strings (e.g., `10080` instead of `"10080"`)

---

## [2.15.1] - 2026-07-29

### Added — Multi-Tenancy for Platform-Level Models

Three platform-level models now support optional team scoping via a nullable `team_id` foreign key to `swx_team.id`. This enables multi-tenant projects to adopt these native models without forking.

---

#### What Changed

- **`LLMProviderConfig`** — Added nullable `team_id` FK. `NULL` = platform-level default provider (visible to all teams). Non-`NULL` = team-specific provider override. Repository functions `get_all()` and `get_by_provider()` accept an optional `team_id` parameter for filtering.

- **`Notification`** — Added nullable `team_id` FK. `NULL` = platform announcement (all users). Non-`NULL` = team-scoped notification. Repository functions `list_notifications()` and `count_notifications()` accept an optional `team_id` parameter.

- **`ApiKey`** — Added nullable `team_id` FK. `NULL` = platform-wide key (admin/service key). Non-`NULL` = team-scoped key. Repository functions `list_api_keys()` and `count_api_keys()` accept an optional `team_id` parameter.

- **Data migration** — `swx_core/database/migrations/v2_15_1_add_team_id_to_platform_models.py` adds the `team_id` column + FK + index to existing databases. Copy to project migrations, set `down_revision`, run `alembic upgrade head`.

- **Template migrations** — The 3 template migrations that create these tables now include the `team_id` column, FK, and index.

- **Docs** — `docs/04-core-concepts/MULTI_TENANT.md` and `docs/07-extending/MULTI_TENANT_MIGRATION.md` updated with the new team-scoping semantics, query patterns, and migration instructions.

---

#### Design Rationale

This follows the industrial-standard nullable `team_id` pattern (used by Stripe, Supabase, GitHub) and matches the existing `UserRole` model in swx-core which already uses nullable `team_id`. The existing `TenantAwareRepository` class and `core/tenant.py` context infrastructure provide automatic tenant filtering for projects that prefer class-based repositories.

---

#### Backward Compatibility

- Existing rows get `team_id = NULL` (platform-level) — behavior unchanged
- All repository functions default `team_id = None` — no filtering when not provided
- No breaking change to existing API responses

---

## [2.15.0] - 2026-07-29

### Changed — Timezone-Aware Timestamps (Breaking)

All timestamps are now timezone-aware. This is a **breaking change** requiring a database migration (`TIMESTAMP WITHOUT TIME ZONE` → `TIMESTAMP WITH TIME ZONE`).

---

#### What Changed

- **New shared utility:** `swx_core/utils/time.py` exports `utc_now()` which returns `datetime.now(timezone.utc)` (timezone-aware). All framework code now imports and uses this instead of stripping timezone info.

- **Eliminated anti-patterns (103 files, 216 occurrences):**
  - Removed all 44 `def utc_now_naive()` helper definitions across model, repository, and service files
  - Replaced all 140 `datetime.now(timezone.utc).replace(tzinfo=None)` calls with `utc_now()`
  - Replaced all 7 production `datetime.utcnow()` calls (Python 3.12 deprecated) with `utc_now()`
  - Removed all inline `lambda: datetime.now(timezone.utc).replace(tzinfo=None)` default factories

- **Database columns:** Changed all `Column(DateTime, ...)` to `Column(DateTime(timezone=True), ...)` across 49 model files, `swx_core/utils/mixins.py`, 15 template migrations, and 2 framework migrations. This creates `TIMESTAMPTZ` columns in PostgreSQL.

- **Data migration:** Added `swx_core/database/migrations/v2_15_0_convert_timestamptz.py` — a dynamic PL/pgSQL migration that converts all existing `TIMESTAMP WITHOUT TIME ZONE` columns in `swx_*` tables to `TIMESTAMPTZ` using `AT TIME ZONE 'UTC'`. Copy to your project's migrations directory, set `down_revision`, and run `alembic upgrade head`.

---

#### Why

Naive timestamps cannot distinguish UTC from local time. If the server timezone changes (container migration, daylight saving, cloud region change), existing timestamps become ambiguous. This affects:

- **Data integrity:** Compliance/audit trails (GDPR, CCPA, SOC 2) require unambiguous timestamps
- **Rate limiting:** Sliding window comparisons assume UTC but nothing enforced it
- **Cache invalidation:** TTL comparisons between cache write and read could shift on timezone mismatch
- **Token expiration:** Token revocation/expiration timestamps could be valid longer than intended

---

#### Migration Guide

1. **Update code:** Install `swx-core>=2.15.0` — all Python code now returns aware datetimes
2. **Run data migration:** Copy `v2_15_0_convert_timestamptz.py` to your project's `migrations/versions/`, set `down_revision` to your current head, run `alembic upgrade head`
3. **Test comparisons:** If your application code compares datetimes from the DB with `datetime.now()`, ensure you use `utc_now()` (or `datetime.now(timezone.utc)`) — comparing aware with naive datetimes raises `TypeError`
4. **Check custom models:** If you have custom models with `Column(DateTime, ...)`, change them to `Column(DateTime(timezone=True), ...)`

---

### Changed Files

| Area | Files | Change |
|---|---|---|
| `swx_core/utils/time.py` | 1 (new) | Shared `utc_now()` utility |
| `swx_core/models/*.py` | 44 | Remove `utc_now_naive`/inline lambdas, import `utc_now`, `Column(DateTime(timezone=True))` |
| `swx_core/utils/mixins.py` | 1 | `FullModelMixin`/`SoftDeleteMixin` use `utc_now`, `DateTime(timezone=True)` |
| `swx_core/repositories/*.py` | 8 | Replace naive timestamp calls with `utc_now()` |
| `swx_core/services/**/*.py` | ~25 | Replace naive timestamp calls with `utc_now()` |
| `swx_core/security/*.py` | 2 | `token_blacklist.py`, `refresh_token_service.py` use `utc_now()` |
| `swx_core/utils/*.py` | 3 | `health.py`, `response.py`, `mixins.py` use `utc_now()` |
| `swx_core/events/*.py` | 2 | `dispatcher.py`, `typed_event.py` use `utc_now()` |
| `swx_core/contracts/*.py` | 1 | `events.py` uses `utc_now()` |
| `swx_core/guards/*.py` | 1 | `api_key_guard.py` uses `utc_now()` |
| `swx_core/cli/commands/resource_templates.py` | 1 | Template string uses `utc_now` |
| `swx_core/services/channels/models.py` | 1 | Uses `utc_now()` |
| Template migrations | 15 | `sa.DateTime()` → `sa.DateTime(timezone=True)` |
| Framework migrations | 2 | `sa.DateTime()` → `sa.DateTime(timezone=True)` |
| `swx_core/database/migrations/v2_15_0_convert_timestamptz.py` | 1 (new) | Data migration: TIMESTAMP → TIMESTAMPTZ |
| `swx_core/version.py` | 1 | Version bump |
| `pyproject.toml` | 1 | Version bump |

---

## [2.14.4] - 2026-07-29

### Fixed — Bug Fixes from FastPII Migration Feedback

Patch release fixing a P0 runtime crash and three P1 issues surfaced during the FastPII Platform migration from v2.7.44 → v2.14.3. All changes are backward compatible.

---

#### P0 Critical

- **`SettingsService._convert_value()` NameError** — `settings_service.py` referenced `SystemConfigValueType` (a non-existent name) instead of the imported `SettingValueType` on lines 165/170/174. Every typed getter (`get_int()`, `get_bool()`, `get_json()`) crashed at runtime. Only `get_string()` survived via the `else` fallthrough. Replaced with the correct `SettingValueType`.

---

#### P1 High

- **Template migrations: branched chain (two heads)** — The 15 template migrations shipped with a branch at `cb96a87ddcc2` producing two alembic heads. Projects copying these migrations had to manually linearize the chain. Rewired `f38a4c8d9b12.down_revision` from `cb96a87ddcc2` to `f7b6d8e0a2c4`, producing a single linear chain with one root and one head.

- **`RateLimitMiddleware._get_user_billing_plan()` always returned `"free"`** — The middleware had two code paths for billing plan resolution: `_actor_from_bearer()` (correctly read the JWT `billing_plan` claim) and `_get_user_billing_plan()` (a stub that hardcoded `return "free"` with dead `EntitlementResolver`/`AsyncSessionLocal` imports). When `request.state.current_user` was pre-resolved by a dependency, the stub path was taken — Pro/Enterprise users got rate-limited as `free`. Replaced the stub with JWT claim decode, consistent with `_actor_from_bearer()`.

- **CSRF helper functions hardcoded `CSRF_COOKIE_NAME`** — `get_csrf_token()` and `set_csrf_cookie()` used the module constant `CSRF_COOKIE_NAME` instead of the middleware instance's `cookie_name`. Projects configuring `CSRFMiddleware(cookie_name="my_csrf_token")` got silent cookie name mismatches when using the helpers. Added a `cookie_name: str = CSRF_COOKIE_NAME` parameter to both helpers (backward-compatible default).

---

#### P3 Minor

- **Dead `lru_cache` import** — `settings_service.py` imported `lru_cache` from `functools` but never used it. Removed.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Replace `SystemConfigValueType` → `SettingValueType` (3 sites); remove dead `lru_cache` import |
| `swx_core/template/project/migrations/versions/f38a4c8d9b12_add_organization_tables.py` | Rewire `down_revision` to `f7b6d8e0a2c4` (linearize chain) |
| `swx_core/middleware/rate_limit_middleware.py` | Replace stubbed `_get_user_billing_plan()` with JWT claim decode |
| `swx_core/middleware/csrf_middleware.py` | Parameterize `cookie_name` on `get_csrf_token()` and `set_csrf_cookie()` |

---

## [2.14.3] - 2026-07-28

### Fixed — Edge Case & Security Hardening (27 issues from comprehensive audit)

Security and robustness fixes across billing, LLM, notification, compliance, and config modules. All changes are backward compatible.

---

#### P0 Critical

- **Sentry middleware: placeholder DSN crashes** — `setup_sentry_middleware()` now validates DSN format via `is_valid_dsn()` before initializing Sentry. Invalid or placeholder DSNs (e.g., `<YOUR_DSN>`) are rejected with a logged warning instead of crashing at runtime.

- **Config resolver: multi-variable substitution bug** — `${HOST:-localhost}:${PORT:-5432}` now correctly resolves to `localhost:5432` instead of `localhost:localhost`. The `_substitute()` method was replaced with a per-match callback in `_resolve_value()` that processes each `${…}` placeholder independently.

- **Config resolver: single-colon default syntax** — `${VAR:default}` (single colon, no dash) is now supported alongside `${VAR:-default}`.

- **Config cache: ValueError on missing env vars** — `resolve_config_value()` in `config_cache.py` now catches `ValueError` from `resolve_config()` when environment variables are missing, returning the fallback value instead of crashing.

- **Stripe provider: mock key bypasses validation** — `get_stripe_provider()` now validates that `sk_live_`/`sk_test_` keys are not mock placeholders (e.g., `sk_test_mock...`). Mock keys no longer pass truthiness checks.

- **Webhook secret: mock secret bypasses validation** — `stripe_webhook.py` webhook handler now rejects `whsec_mock` and similar mock secrets via `is_valid_webhook_secret()`.

- **Billing provider: Stripe key format validation** — `billing_provider.py` now validates Stripe API key prefix (`sk_live_`/`sk_test_`) and rejects placeholder patterns before making API calls.

---

#### P1 High

- **Billing providers: HTTP error handling** — Flutterwave, Paystack, and Mpesa providers now catch `httpx` transport and HTTP status errors, log them with `logger.exception()`, and re-raise as `HTTPException(503)` for consistent upstream error handling.

- **Subscription service: rollback on write failures** — All four `session.add()`/`session.commit()` write paths in `subscription_service.py` now wrap operations in `try/except`, call `await session.rollback()`, log the error, and re-raise.

- **LLM providers: error logging in fallback paths** — `openai_provider.py`, `azure_provider.py`, `anthropic_provider.py`, and `ollama_provider.py` now log `logger.error()` inside their existing `except Exception as exc` blocks instead of silently swallowing errors during fallback.

- **Notification providers: graceful failure handling** — `twilio_provider.py`, `sendgrid_provider.py`, `africas_talking_provider.py`, and `smtp_provider.py` now catch HTTP/SMTP transport errors, log stack traces, and return structured failure payloads instead of raising exceptions upstream.

- **Sentry middleware: init guard** — `SentryMiddleware.__init__()` now wraps SDK initialization in `try/except` so a misconfigured DSN or network failure doesn't prevent the entire app from starting.

---

#### P2 Infrastructure

- **New module: `swx_core/config/validation.py`** — Shared validation utilities (`is_valid_config_value`, `is_valid_api_key`, `is_valid_dsn`, `is_valid_redis_url`, `is_valid_webhook_secret`) for checking that config values are not placeholders, mocks, or malformed. Exported via `swx_core.config.__init__`.

- **Security validation strengthened** — `security_validation.py` Python identifier checks, keyword detection, and path traversal patterns improved for stricter input validation.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/config/validation.py` | **New** — Shared config validation utilities |
| `swx_core/config/__init__.py` | Export validation functions |
| `swx_core/middleware/sentry_middleware.py` | DSN validation + try/except init guard |
| `swx_core/services/llm/config_resolver.py` | Multi-variable substitution fix, single-colon syntax support |
| `swx_core/services/compliance/config_cache.py` | ValueError handling on missing env vars |
| `swx_core/services/billing/stripe_provider.py` | Mock key validation |
| `swx_core/providers/billing_provider.py` | Stripe API key format validation |
| `swx_core/webhooks/stripe_webhook.py` | Webhook secret mock rejection |
| `swx_core/services/billing/providers/flutterwave_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/providers/paystack_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/providers/mpesa_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/subscription_service.py` | Rollback on write failures + logging |
| `swx_core/services/llm/providers/openai_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/azure_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/anthropic_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/ollama_provider.py` | Error logging in fallback path |
| `swx_core/services/notifications/providers/twilio_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/sendgrid_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/africas_talking_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/smtp_provider.py` | Graceful failure handling + logging |
| `swx_core/cli/commands/security_validation.py` | Strengthened identifier/keyword/path validation |

**Backward Compatibility:** Fully backward compatible. All fixes are defensive — they add validation, logging, and error handling without changing any public APIs or behavior for correctly configured systems.

---

## [2.14.2] - 2026-07-28

### Fixed — Test Suite Hardening

- **244 tests passing, 2 skipped (passlib) — 100% pass rate**
- Fixed `security_validation.py` Python identifier validation, keyword checking, and path traversal patterns
- Completed `SimpleNamespace` mock attributes for API key scoping tests
- Added `passlib` import skip for environments without passlib installed
- Exported `FEATURE_FLAG_CACHE_TTL` module-level constant from settings
- Fixed env var syntax in compliance service tests (`${VAR}` → `${VAR}`)
- Fixed mask assertion in compliance event tests
- Fixed template key assertions in webhook service tests

---

## [2.14.1] - 2026-07-28

### Fixed — Tier 3 Test Fixes

- Fixed all Tier 3 feature test failures (Conversation State, AI Safety, Enterprise SSO, Status Page, Data Transfer, Feature Flags)
- Corrected model field references, import paths, and test assertions

---

## [2.14.0] - 2026-07-28

### Added — Tier 3 Feature Suite (6 enterprise features)

Six production-grade features following the SwX Repository → Service → Controller → Route pattern with event emission, caching, and database-driven configuration.

#### 10. Conversation State
#### 11. AI Safety & Content Filtering
#### 12. Enterprise SSO
#### 13. Status Page
#### 14. Data Export/Import
#### 15. Feature Flags & A/B Testing

*(See v2.14.0 detailed changelog in docs/11-reference/CHANGELOG.md)*

---

## [2.13.0] - 2026-07-28

### Added — Tier 2 Feature Suite (4 enterprise features)

Four production-grade features following the SwX Repository → Service → Controller → Route pattern with event emission, caching where appropriate, database-driven configuration, and full documentation.

---

#### 6. Compliance Audit

GDPR/CCPA-compliant audit logging with severity levels, data classification, field redaction, IP masking, retention policies, and data subject request handling (access, deletion, portability, rectification, restriction).

**New tables:** `swx_compliance_config`, `swx_data_subject_request`, `swx_retention_policy`

**Extended models:** AuditLog gains `severity`, `data_classification`, `access_result`, `masked_ip` fields. AuditOutcome enum gains `DENIED_INSUFFICIENT_ROLE`, `DENIED_CONSENT_REQUIRED`, `DENIED_DATA_CLASSIFICATION`, `DENIED_POLICY`.

**Events:** `compliance.data_accessed`, `compliance.consent_violation`, `compliance.data_exported`, `compliance.config_updated`, `compliance.data_subject_request_created`

**Caching:** Compliance config cached with 30s TTL, invalidated on CRUD.

**Auto-masking:** AuditLogger automatically masks IPs and redacts sensitive fields based on compliance config.

**Endpoints:** Admin (`/admin/compliance/*`), User GDPR (`/user/gdpr/*`)

**Files:** 6 new service modules, 3 models, 1 repository, 2 controllers, 4 route modules. Migration: `d1f6e4a9c3b2`.

---

#### 7. Notification Factory

Multi-provider notification system with circuit breaker fallback, Jinja2 template rendering, delivery tracking, and preference management. Supports SMTP, SendGrid, Twilio, and Africa's Talking.

**New tables:** `swx_email_provider_config`, `swx_sms_provider_config`, `swx_notification`, `swx_notification_preference`, `swx_notification_template`

**Events:** `notification.sent`, `notification.failed`, `notification.template_created`, `notification.preference_updated`

**Caching:** Provider configs cached indefinitely (keyed by config hash). Templates cached with 30s TTL.

**Provider fallback:** Circuit breaker per provider with automatic failover to next provider in chain.

**Endpoints:** Admin (`/admin/notifications/*`), User (`/user/notifications/*`)

**Files:** 7 service modules + 4 provider implementations, 5 models, 1 repository, 1 controller, 4 route modules. Migration: `e7a3c1b2d4f5`.

---

#### 8. API Key Scoping

SHA-256 hashed API key management with resource:action scope patterns, wildcards, key rotation with grace period, and per-key rate limit overrides.

**New tables:** `swx_api_key`, `swx_api_key_scope`

**Events:** `api_key.created`, `api_key.revoked`, `api_key.rotated`, `api_key.scope_changed`

**Key rotation:** Grace period (`API_KEY_ROTATION_GRACE_HOURS`, default 24h) allows both old and new keys during transition.

**Scope patterns:** `resource:action` (e.g., `users:read`), `resource:*` (all actions), `*:read` (read across resources), `*:*` (full access).

**Endpoints:** Admin (`/admin/api-keys/*`), User (`/user/api-keys/*`)

**Files:** 2 models, 1 repository, 2 services, 1 controller, 4 route modules. Migration: `f8b2d5e7a1c3`.

---

#### 9. Webhook System

Outbound webhook delivery with HMAC-SHA256 signature verification, circuit breaker per endpoint, exponential backoff retry with jitter, wildcard event subscription matching, and delivery status tracking.

**New tables:** `swx_webhook_endpoint`, `swx_webhook_delivery`, `swx_webhook_event`

**Events:** `webhook.endpoint_created`, `webhook.endpoint_updated`, `webhook.endpoint_deleted`, `webhook.delivery_created`, `webhook.delivery_delivered`, `webhook.delivery_retrying`, `webhook.delivery_failed`, `webhook.delivery_retry_requested`, `webhook.subscription_updated`

**Signing:** HMAC-SHA256 with `${ENV_VAR}` secret resolution via config_resolver.

**Retry:** Exponential backoff with jitter, configurable retry count/delay/timeout per endpoint. Circuit breaker per endpoint using existing resilience module.

**Wildcard matching:** `user.*` matches `user.created`, `user.updated`, etc. `*` matches all events.

**Endpoints:** Admin (`/admin/webhooks/*`), User (`/user/webhooks/*`)

**Files:** 4 service modules, 3 models, 1 repository, 1 controller, 4 route modules. Migration: `a91c4e2f7b6d`.

---

### Migration Chain

```
d1f6e4a9c3b2 (compliance audit)
  → e7a3c1b2d4f5 (notification factory)
    → f8b2d5e7a1c3 (api key scoping)
      → a91c4e2f7b6d (webhook system)
```

### Configuration

All new settings use database-driven defaults with `${ENV_VAR}` credential resolution:

| Setting | Default | Description |
|---|---|---|
| `COMPLIANCE_ENABLED` | `True` | Enable compliance audit logging |
| `COMPLIANCE_DEFAULT_SEVERITY` | `"medium"` | Default audit log severity |
| `COMPLIANCE_DEFAULT_DATA_CLASSIFICATION` | `"internal"` | Default data classification |
| `COMPLIANCE_IP_MASKING_ENABLED` | `True` | Auto-mask IPs in audit logs |
| `COMPLIANCE_FIELD_REDACTION_ENABLED` | `True` | Auto-redact sensitive fields |
| `NOTIFICATION_ENABLED` | `True` | Enable notification system |
| `NOTIFICATION_DEFAULT_PROVIDER_CHAIN` | `"smtp"` | Default provider fallback chain |
| `NOTIFICATION_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `NOTIFICATION_TEMPLATE_CACHE_TTL` | `30` | Template cache TTL in seconds |
| `API_KEY_ROTATION_GRACE_HOURS` | `24` | Hours both keys valid during rotation |
| `WEBHOOK_ENABLED` | `True` | Enable outbound webhooks |
| `WEBHOOK_DEFAULT_RETRY_COUNT` | `3` | Default retry count per delivery |
| `WEBHOOK_DEFAULT_RETRY_DELAY` | `60` | Default retry delay in seconds |
| `WEBHOOK_DEFAULT_TIMEOUT` | `30` | Default HTTP timeout in seconds |
| `WEBHOOK_MAX_RETRIES` | `10` | Maximum retries across all deliveries |
| `WEBHOOK_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |

### Documentation

New docs added under `docs/04-core-concepts/`:
- `COMPLIANCE_AUDIT.md`
- `NOTIFICATION_FACTORY.md`
- `API_KEY_SCOPING.md`
- `WEBHOOK_SYSTEM.md`

### Tests

New test files:
- `tests/services/test_compliance_events.py`
- `tests/services/test_compliance_services.py`
- `tests/services/test_api_key_scoping.py`
- `tests/services/test_webhook_services.py`
- `tests/bootstrap/test_webhook_routes.py`

## [2.12.0] - 2026-07-28

### Added — Tier 1 Feature Suite (5 enterprise features)

Five production-grade features requested by AFCloud AI, each following the SwX Repository → Service → Controller → Route pattern with event emission, caching where appropriate, database-driven configuration, and full documentation.

---

#### 1. Consent Management

GDPR/CCPA-compliant consent tracking with configurable consent types, versioning, and enforcement hooks.

**New tables:** `swx_consent_type`, `swx_user_consent`, `swx_consent_version`

**Events:** `consent.granted`, `consent.withdrawn`, `consent.expired`

**Caching:** Consent enforcement checks cached with 30s TTL, invalidated on grant/withdraw.

**Endpoints:** Admin (manage types, view all consents), User (grant, withdraw, view status).

**Files:** 9 new, 3 modified. Migration: `cb96a87ddcc2`.

---

#### 2. Organization Model

Multi-tenant organization support with roles (Owner/Admin/Member), invitations, and member management.

**New tables:** `swx_organization`, `swx_organization_member`, `swx_organization_invitation`

**Events:** `organization.created`, `organization.updated`, `organization.deleted`, `organization.invitation_sent`, `organization.member_joined`, `organization.member_removed`, `organization.member_role_changed`

**Endpoints:** Admin (view all), User (create, update, delete, invite, accept, reject, members, roles).

**Files:** 8 new, 3 modified. Migration: `f38a4c8d9b12`.

---

#### 3. Append-Only Ledger

Immutable financial ledger with running balances, idempotency, refunds, transfers, and reconciliation.

**New tables:** `swx_ledger_entry`, `swx_ledger_balance`, `swx_ledger_idempotency`

**Events:** `ledger.credit`, `ledger.debit`, `ledger.refund`, `ledger.transfer`

**Design:** All entries immutable (insert-only). Amounts in nano-units (int). `LedgerBalance` table serves as a cached balance. `metadata_` column name avoids SQLAlchemy reserved word collision while serializing as `metadata` in API responses.

**Endpoints:** Admin (credit, debit, refund, transfer, balance, history, reconcile).

**Files:** 6 new, 2 modified. Migration: `9b2f6c1d4a7e`.

---

#### 4. LLM Provider Service

Multi-provider LLM abstraction with circuit breaker, retry with jitter, timeout enforcement, and provider fallback chains. Supports OpenAI, Azure, Anthropic, and Ollama.

**New tables:** `swx_llm_provider_config`, `swx_llm_usage_log`

**Events:** `llm.generate`, `llm.provider_failed`

**Caching:** Provider instances cached indefinitely (keyed by config hash). Provider chain cached per phase with 60s TTL, invalidated on any provider config CRUD.

**DB-driven configuration:** Per-provider resilience settings (timeout, retries, circuit breaker threshold/reset, rate limits, daily token limits) stored in database with global settings fallback.

**Credential resolution:** `${ENV_VAR}` (required) and `${ENV_VAR:-default}` (optional) placeholder patterns resolved at runtime.

**Files:** ~20 new, 3 modified. Migration: `c41b7a8e2f10`.

---

#### 5. Multi-Currency Billing

Multi-currency wallet system with 3 African payment providers, exchange rate management, and jurisdiction-specific tax calculation.

**New tables:** `swx_currency`, `swx_exchange_rate`, `swx_wallet`

**Events:** `wallet.credit`, `wallet.debit`, `wallet.transfer`

**Wallet ↔ Ledger integration:** Each wallet uses its `wallet.id` as the ledger `account_id`, ensuring per-currency balance isolation.

**Payment providers:** Paystack (NG, GH), Flutterwave (NG, KE, ZA, GH), M-Pesa (KE). All use `${ENV_VAR}` credential resolution.

**Exchange rate resolution:** Three-tier fallback (direct → inverse → pivot through base currency).

**Tax engine:** NG 7.5%, KE 16%, ZA 15%, GH 15%, US 0%, GB 20%.

**Default currencies:** USD (base), NGN, KES, ZAR, GHS.

**Files:** 16 new, 3 modified. Migration: `b7e1c2d3f4a5`.

---

### Migration Chain

```
cb96a87ddcc2 (consent)
  → f38a4c8d9b12 (organization)
    → 9b2f6c1d4a7e (ledger)
      → c41b7a8e2f10 (llm)
        → b7e1c2d3f4a5 (multi-currency)
```

### Documentation

New docs added under `docs/04-core-concepts/`:
- `CONSENT_MANAGEMENT.md`
- `ORGANIZATIONS.md`
- `LEDGER.md`
- `LLM_PROVIDER.md`
- `MULTI_CURRENCY.md`

## [2.9.0] - 2026-07-22

### Added - Database Engine Configuration via Environment Variables

**Configurable connection pooling and statement timeout** — allows production deployments to tune database connections without forking swx-core.

Previously, all pool parameters were hardcoded in `db.py` with no way to adjust them for production workloads. This caused connection exhaustion under high concurrency.

**New settings:**

| Setting | Default | Description |
|---|---|---|
| `DB_POOL_SIZE` | `20` | Base connection pool size for async engine |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections beyond pool_size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a connection from pool |
| `DB_POOL_RECYCLE` | `3600` | Seconds before recycling a connection |
| `DB_POOL_USE_LIFO` | `False` | Use LIFO connection reuse (warmer connections) |
| `DB_STATEMENT_TIMEOUT_MS` | `0` | PostgreSQL statement timeout in ms (0 = disabled) |
| `DB_SYNC_POOL_SIZE` | `5` | Base pool size for sync engine (Celery workers) |
| `DB_SYNC_MAX_OVERFLOW` | `5` | Max overflow for sync engine |

**Backward compatible:** All defaults match the previous hardcoded values. No changes needed for existing deployments.

**Recommended production values for high-concurrency:**

```env
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_POOL_USE_LIFO=true
DB_STATEMENT_TIMEOUT_MS=30000
```

**Files Changed:**
- `swx_core/config/settings.py` - MODIFIED: Added 8 database pool configuration settings
- `swx_core/database/db.py` - MODIFIED: Async and sync engines now use configurable pool settings, added statement_timeout support

## [2.8.0] - 2026-07-22

### Added - User Auth Caching (L1/L2 Redis)

**Redis-backed two-level cache for auth lookups** — dramatically reduces database queries on every authenticated request.

- L1 cache: process-local dict with timestamp-based TTL (zero Redis round-trip)
- L2 cache: Redis with structured key naming `{env}:{app}:{scope}:{resource}:{identifier}:{version}`
- Cacheable fields exclude `hashed_password` for security
- Graceful degradation: if Redis is unavailable, falls back to L1-only then DB
- Backward compatible: `USER_CACHE_ENABLED=False` (default) = no caching

**New settings:**

| Setting | Default | Description |
|---|---|---|
| `USER_CACHE_ENABLED` | `False` | Enable L1/L2 cache for user auth lookups |
| `USER_CACHE_TTL` | `300` | TTL in seconds for cached user profiles |
| `USER_PERMISSIONS_CACHE_TTL` | `120` | TTL in seconds for cached user permissions |
| `USER_CACHE_L1_MAX_ENTRIES` | `1000` | Maximum entries in process-local L1 cache |
| `ADMIN_CACHE_ENABLED` | `False` | Enable L1/L2 cache for admin auth lookups |
| `ADMIN_CACHE_TTL` | `300` | TTL in seconds for cached admin profiles |

**Cached paths:**

- `get_current_user()` — checks L1 → L2 → DB, populates L1+L2 on miss
- `get_current_admin_user()` — checks L1 → L2 → DB, populates L1+L2 on miss
- `get_user_permissions()` — checks L1 → L2 → DB, populates L1+L2 on miss

**Cache invalidation hooks:**

- `update_user_profile_service()` → invalidates user profile cache (by id + email)
- `update_password_service()` → invalidates user profile cache
- `delete_user_service()` → invalidates user profile cache
- `assign_role_to_user_service()` → invalidates user permissions cache
- `remove_role_from_user_service()` → invalidates user permissions cache
- `assign_permission_to_role_service()` → invalidates ALL permission caches
- `remove_permission_from_role_service()` → invalidates ALL permission caches

**Files Changed:**
- `swx_core/config/settings.py` - MODIFIED: Added auth cache configuration settings
- `swx_core/auth/auth_cache.py` - NEW: AuthCache class with L1/L2, invalidation functions
- `swx_core/auth/user/dependencies.py` - MODIFIED: get_current_user() now checks cache first
- `swx_core/auth/admin/dependencies.py` - MODIFIED: get_current_admin_user() now checks cache first
- `swx_core/rbac/helpers.py` - MODIFIED: get_user_permissions() now checks cache first
- `swx_core/services/user_service.py` - MODIFIED: Added cache invalidation after profile/password/delete
- `swx_core/services/user_role_service.py` - MODIFIED: Added cache invalidation after role assign/remove
- `swx_core/services/role_service.py` - MODIFIED: Added cache invalidation after permission assign/remove
- `docs/04-core-concepts/AUTHENTICATION.md` - MODIFIED: Added auth caching documentation

## [2.7.45] - 2026-07-22

### Added - Admin Auth: Refresh Tokens, Cookie Routes, and Modular Architecture

**Admin login now returns refresh tokens** (previously returned `refresh_token: null`):

- `POST /api/admin/auth/` now returns both `access_token` and `refresh_token`
- `POST /api/admin/auth/refresh` — new endpoint to refresh admin access tokens
- `POST /api/admin/auth/revoke` — new endpoint to revoke admin refresh tokens (logout)

**Admin cookie-based authentication** (BFF pattern for browser admin panels):

- `POST /api/admin/auth/cookie/login` — authenticate and set httpOnly cookies
- `POST /api/admin/auth/cookie/refresh` — refresh tokens via httpOnly cookies
- `POST /api/admin/auth/cookie/logout` — clear httpOnly auth cookies

**Architecture: Refactored admin auth into Repository-Service-Controller-Route pattern:**

- `swx_core/repositories/admin_user_repository.py` — `get_admin_by_email()`, `authenticate_admin()`
- `swx_core/services/admin_auth_service.py` — `login_admin_service()`, `refresh_admin_token_service()`, `logout_admin_service()`, `verify_admin_cookie_refresh()`, `set_auth_cookies()`, `clear_auth_cookies()`
- `swx_core/controllers/admin_auth_controller.py` — Thin delegation layer
- `swx_core/routes/admin/auth_route.py` — Core auth endpoints (login, refresh, revoke)
- `swx_core/routes/admin/auth_cookie_route.py` — Cookie auth endpoints (cookie/login, cookie/refresh, cookie/logout)

**Documentation:**

- Updated AUTHENTICATION.md with admin refresh token flow, admin cookie auth endpoints, and frontend examples

**Files Changed:**
- `swx_core/repositories/admin_user_repository.py` - NEW: Admin user repository
- `swx_core/services/admin_auth_service.py` - NEW: Admin auth business logic
- `swx_core/controllers/admin_auth_controller.py` - NEW: Admin auth controller
- `swx_core/routes/admin/auth_route.py` - MODIFIED: Refactored to use controller/service, added refresh/revoke endpoints
- `swx_core/routes/admin/auth_cookie_route.py` - NEW: Admin cookie auth endpoints
- `swx_core/routes/admin/__init__.py` - MODIFIED: Added auth_cookie_router
- `docs/04-core-concepts/AUTHENTICATION.md` - MODIFIED: Updated admin auth docs

## [2.7.44] - 2026-07-13

### Fixed - router_module() Doubles /api/v1 Prefix for Versioned Routes

**Priority:** Medium — causes incorrect URL paths for production API endpoints

#### BUG: router_module() doubles /api/v1 prefix and cannot produce root-level API paths

**Problem:** `router_module()` composes final URL paths as `include_prefix + router.prefix + route.path`. For versioned routes, `include_prefix` is `/api/v1`. If a route module sets `prefix="/api/v1"` on its APIRouter, the result is a doubled prefix: `/api/v1/api/v1/detect/batch`. Additionally, auto-generated prefixes for versioned routes included a duplicate version segment (`/api/v1/v1/detection_api/detect`), and there was no way to opt out of prefix generation for root-level paths.

**Fix:** Three changes to `router_module()`:

1. **Strip `/api/{version}` from user-defined prefix** for versioned routes — prevents doubling when a module sets `prefix="/api/v1"`
2. **Strip version segment from auto-generated prefix** — auto-generated prefixes for versioned routes no longer include the version segment since it's already in `include_prefix`
3. **Support module-level `ROUTE_PREFIX` attribute** — allows explicit empty prefix opt-out via `ROUTE_PREFIX = ""` for root-level versioned paths

**Files Changed:**
- `swx_core/router.py` - Fixed prefix composition logic in `router_module()`

**URL path resolution examples (after fix):**

| Module | Router Prefix | Result Path |
|---|---|---|
| `app/routes/v1/auth.py` | `prefix=""` | `/api/v1/auth` |
| `app/routes/v1/auth.py` | `prefix="/auth"` | `/api/v1/auth` |
| `app/routes/v1/auth.py` | `prefix="/api/v1/auth"` | `/api/v1/auth` (stripped) |
| `app/routes/v1/detect.py` | `ROUTE_PREFIX="/"` | `/api/v1` (root-level) |
| `app/routes/v1/detect.py` | `ROUTE_PREFIX=""` | `/api/v1/detect` (auto) |

## [2.7.43] - 2026-07-12

### Fixed - BillingServiceProvider Boot Failure

**Priority:** P0 (Prevents billing from booting on startup)

#### BUG: FeatureRegistry.register() called with keyword arguments instead of FeatureDefinition object

**Problem:** `BillingServiceProvider._register_default_features()` called `registry.register()` with keyword arguments (`key=`, `name=`, `default_value=`, etc.), but `FeatureRegistry.register()` expects a single `FeatureDefinition` positional argument. Additionally, `default_value` is not a field on `FeatureDefinition`. This caused the entire billing service to fail to boot when `BILLING_ENABLED=true`.

**Symptoms:**
- Error: `FeatureRegistry.register() got an unexpected keyword argument 'key'`
- No billing provider initialized
- No subscription service available
- All billing API endpoints return errors

**Fix:** Replaced keyword argument calls with `FeatureDefinition` objects, removed nonexistent `default_value`, added `unit` for QUOTA features, and added deduplication check to avoid overwriting app-specific features.

**Files Changed:**
- `swx_core/providers/billing_provider.py` - `_register_default_features` now creates `FeatureDefinition` objects and deduplicates against existing registrations

## [2.7.42] - 2026-07-12

### Fixed - Critical Stripe Billing Bugs

**Priority:** P0 (Production checkout is broken without these fixes)

#### BUG-1: create_checkout_session passes database UUID as Stripe price ID

**Problem:** `StripeProvider.create_checkout_session()` passed `plan_id` (a database UUID like `550e8400-e29b-41d4-a716-446655440000`) to Stripe's `price` field, which expects a `price_xxx` identifier. Every checkout attempt failed with `resource_missing` error.

**Fix:** Added `stripe_price_id` and `stripe_product_id` columns to the `Plan` model. Renamed the provider parameter from `plan_id` to `price_id` across all billing interfaces. The controller now resolves the Plan's `stripe_price_id` before passing it to Stripe.

**Files Changed:**
- `swx_core/models/billing.py` - Added `stripe_price_id`, `stripe_product_id`, `amount`, `currency` to Plan model
- `swx_core/services/billing/stripe_provider.py` - `create_checkout_session` now takes `price_id` instead of `plan_id`
- `swx_core/services/billing/billing_provider_base.py` - Updated interface: `plan_id` → `price_id`
- `swx_core/providers/billing_provider.py` - Updated MockBillingProvider interface

**Migration Required:** Add `stripe_price_id`, `stripe_product_id`, `amount`, `currency` columns to `swx_billing_plan` table.

#### BUG-2: sync_stripe_subscription cannot create new subscriptions from webhooks

**Problem:** When Stripe sent `customer.subscription.created`, the webhook handler silently dropped the event because no local subscription existed yet. Only subscriptions created via direct DB seeding persisted.

**Fix:** `sync_stripe_subscription` now creates a local `Subscription` record when no existing match is found. It resolves the Stripe price ID to a local Plan via `stripe_price_id` and the Stripe customer ID to a local BillingAccount.

**Files Changed:**
- `swx_core/services/billing/subscription_service.py` - Added subscription creation from webhook events with Plan and BillingAccount resolution

#### BUG-3: create_portal_session returns stub response

**Problem:** `StripeProvider` had no `create_portal_session` implementation. Users couldn't manage subscriptions (cancel, upgrade, update payment method) without admin intervention.

**Fix:** Implemented `create_portal_session` in both `StripeProvider` and `MockBillingProvider` using `stripe.billing_portal.Session.create`.

**Files Changed:**
- `swx_core/services/billing/stripe_provider.py` - Added `create_portal_session` method
- `swx_core/services/billing/billing_provider_base.py` - Added `create_portal_session` to interface
- `swx_core/providers/billing_provider.py` - Added `create_portal_session` to MockBillingProvider

#### BUG-4: Missing checkout.session.completed webhook handler

**Problem:** The webhook handler only processed `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. The `checkout.session.completed` event was missing, causing delayed subscription sync.

**Fix:** Added `checkout.session.completed` handling in the webhook job handler. It extracts the subscription ID from the checkout session and syncs the full Stripe subscription data.

**Files Changed:**
- `swx_core/services/job/handlers.py` - Added `checkout.session.completed` event handling

### Code Clarity Applied

Extracted helper functions to eliminate repeated logic:
- `_utc_now_naive()` in `billing.py` for timestamp defaults
- `_serialize_metadata()` in `stripe_provider.py` for Stripe metadata normalization
- `_naive_utc_from_timestamp()` and `_resolve_stripe_price_id()` in `subscription_service.py`
- `SUBSCRIPTION_SYNC_EVENT_TYPES` constant in `handlers.py`

## [2.7.41] - 2026-07-05

### Fixed - Critical Bugs from v2.7.40

**Priority:** P0 (Critical production bugs)

#### BUG-1: InvitationStatus StrEnum Case Mismatch with PostgreSQL ENUM

**Problem:** `InvitationStatus` enum used lowercase values (`"pending"`, `"accepted"`, etc.) but PostgreSQL ENUM columns are case-sensitive. When asyncpg binds parameters, it uses the enum's `.name` attribute which is UPPERCASE (`PENDING`, `ACCEPTED`), causing PostgreSQL to reject values.

**Symptoms:**
- All `TeamInvitationService` queries filtering by `InvitationStatus.PENDING` failed with HTTP 500
- Error: `invalid input value for enum invitationstatus: "PENDING"`

**Fix:** Changed `InvitationStatus` enum values to uppercase to match PostgreSQL ENUM expectations:
```python
# BEFORE
class InvitationStatus(str, Enum):
    PENDING = "pending"    # lowercase
    ACCEPTED = "accepted"  # lowercase

# AFTER
class InvitationStatus(str, Enum):
    PENDING = "PENDING"    # uppercase
    ACCEPTED = "ACCEPTED"  # uppercase
```

**Migration Required:** If you created PostgreSQL enums with lowercase values:
```sql
DROP TYPE IF EXISTS invitationstatus CASCADE;
CREATE TYPE invitationstatus AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'REVOKED');
```

**Files Changed:**
- `swx_core/models/team_invitation.py` - Updated InvitationStatus enum values

#### BUG-2: swx_team_member.role_id NOT NULL Constraint Violation

**Problem:** The v2.7.40 model removed `role_id` from `TeamMember` (replaced by `team_role_id`), but the database column still exists as `NOT NULL` with no default. Creating team members only provides `team_role_id`, leaving `role_id` as NULL - which violates the constraint.

**Symptoms:**
- POST `/admin/team/member` failed with HTTP 500
- Error: `null value in column "role_id" of relation "swx_team_member" violates not-null constraint`

**Fix:** Users need to run a migration to make `role_id` nullable or drop the column entirely.

**Migration Required:** See `MIGRATION_GUIDE_v2.7.41.md` for detailed migration steps:
```python
# Migration: make_team_member_role_id_nullable
def upgrade() -> None:
    op.alter_column(
        'swx_team_member',
        'role_id',
        existing_type=sa.UUID(),
        nullable=True
    )
```

**Workaround Applied:** Users who already fixed this can skip the migration.

**Files Changed:**
- `MIGRATION_GUIDE_v2.7.41.md` - Added comprehensive migration guide
- No model changes (model is correct, database needs migration)

### Migration Guide

See [MIGRATION_GUIDE_v2.7.41.md](./MIGRATION_GUIDE_v2.7.41.md) for:
- Detailed migration steps
- Verification procedures
- Rollback instructions
- Database schema changes

### Breaking Changes

**None** - These are pure bug fixes with no breaking API changes.

### Verification Steps

1. **InvitationStatus Fix:**
   ```bash
   curl -X POST http://localhost:8001/api/admin/team/invite \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"team_id": "...", "invitee_email": "test@example.com", "team_role_id": "..."}'
   # Should return 200 OK, not 500
   ```

2. **Team Member Creation:**
   ```bash
   curl -X POST http://localhost:8001/api/admin/team/member \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"team_id": "...", "user_id": "...", "team_role_id": "..."}'
   # Should return 200 OK, not 500
   ```

## [2.7.40] - 2026-07-05

### Added - Enterprise Dashboard Features

**Priority:** P2 (4 feature requests from FastPII Integration)

#### FEATURE-1: User-Scoped Workspace Endpoints

**Added:** New workspace endpoints for Enterprise Dashboard with user-scoped filtering.

**Endpoints:**
- `GET /api/v1/workspaces` - List workspaces for current user
- `GET /api/v1/workspaces/{workspace_id}` - Get workspace detail
- `POST /api/v1/workspaces` - Create workspace
- `PUT /api/v1/workspaces/{workspace_id}` - Update workspace
- `DELETE /api/v1/workspaces/{workspace_id}` - Archive workspace

**Implementation:**
- New route: `swx_core/routes/user/workspace_route.py`
- New controller: `swx_core/controllers/workspace_controller.py`
- User filtering: Lists only teams where `current_user.id` is a member via TeamMember
- Uses existing Team model and TeamService
- Authentication: `Depends(get_current_user)`

**Use Case:** Enterprise Dashboard workspace management with user-specific workspace list.

#### FEATURE-2: Enriched Team Member Endpoint

**Added:** New endpoint returning team members with full user and role details.

**Endpoint:**
- `GET /api/admin/team/{team_id}/members/enriched` - List members with enriched details

**Response Schema:**
```json
{
  "id": "...",
  "team_id": "...",
  "user": {
    "id": "...",
    "email": "...",
    "full_name": "...",
    "avatar_url": "..."
  },
  "team_role": {
    "id": "...",
    "key": "owner",
    "name": "Team Owner",
    "permissions": {...}
  },
  "created_at": "..."
}
```

**Implementation:**
- New schema: `TeamMemberWithDetails` (swx_core/models/team_member.py)
- Uses `joinedload(User)` and `joinedload(TeamRole)` for eager loading
- Original endpoint preserved: `GET /api/admin/team/{team_id}/members` (IDs only)

**Use Case:** Enterprise Dashboard team member management with full user context.

#### FEATURE-3: Team Invitation Auto-Accept on Registration

**Added:** Auto-accept team invitations when users register through invitation links.

**Flow:**
1. User receives invitation email with link
2. User clicks link → redirected to registration
3. Frontend passes `invitation_token` in registration request
4. Backend creates user account
5. `post_register_hook` automatically accepts invitation
6. User added to team immediately

**Implementation:**
- New hook: `swx_core/hooks/invitation_auto_accept.py`
- Registered in `swx_core/core/hooks.py` via `registration_hooks.add_post_register()`
- `UserCreate` schema accepts optional `invitation_token` field
- `register_user_service` passes token through `event_context`
- Hook validates email match (invitation.invitee_email == user.email)
- Error handling: Hook failures log warning but don't block registration

**Security:**
- Email validation enforced by TeamInvitationService
- Token expiration enforced (7 days default)
- Invitation must have status PENDING

**Use Case:** Seamless onboarding when inviting new users to teams.

#### FEATURE-4: Team Invitation Event Emission

**Added:** Event emission for team invitation creation to enable email notifications.

**Event Bus:**
- Location: `swx_core/event_bus.py` (AsyncEventBus)
- Event type: `team.invitation.created`
- Event class: `TeamInvitationCreatedEvent`

**Event Payload:**
```json
{
  "invitation_id": "uuid",
  "team_id": "uuid",
  "inviter_id": "uuid",
  "invitee_email": "string",
  "token": "string",
  "metadata": {"invitation_code": "string"}
}
```

**Implementation:**
- TeamInvitationService.create_invitation() emits event after successful creation
- Event emission is asynchronous (doesn't block invitation creation)
- FastPII can subscribe to `team.invitation.created` for email sending

**Example Handler (FastPII):**
```python
@event_bus.subscribe("team.invitation.created")
async def send_invitation_email(event):
    await send_email(
        to=event.invitee_email,
        template="team_invitation",
        data={"team_name": event.team_name, "token": event.token}
    )
```

**Use Case:** Enable FastPII email notification system for team invitations.

### Files Modified

- `swx_core/routes/user/workspace_route.py` - NEW: User-scoped workspace endpoints
- `swx_core/controllers/workspace_controller.py` - NEW: Workspace controller
- `swx_core/models/team_member.py` - NEW: TeamMemberWithDetails schema
- `swx_core/routes/admin/team_route.py` - NEW: Enriched members endpoint
- `swx_core/hooks/invitation_auto_accept.py` - NEW: Auto-accept hook
- `swx_core/core/hooks.py` - UPDATED: Hook registration
- `swx_core/services/team_invitation_service.py` - UPDATED: Event emission
- `swx_core/events/__init__.py` - UPDATED: TeamInvitationCreatedEvent
- `swx_core/main.py` - UPDATED: Route registration

### Migration Guide

**No database migrations required** - all changes are code additions.

**Configuration:**
1. Import and register workspace routes in your app:
   ```python
   from swx_core.routes.user.workspace_route import router as workspace_router
   app.include_router(workspace_router, prefix="/api/v1/workspaces")
   ```

2. Register auto-accept hook at startup:
   ```python
   from swx_core.hooks.invitation_auto_accept import auto_accept_invitation
   from swx_core.core.hooks import registration_hooks
   registration_hooks.add_post_register(auto_accept_invitation)
   ```

3. Subscribe to invitation events (FastPII):
   ```python
   from swx_core.event_bus import event_bus
   
   @event_bus.subscribe("team.invitation.created")
   async def send_invitation_email(event):
       # Your email logic
   ```

### Breaking Changes

None - all changes are additive and backward compatible.

---

## [2.7.39] - 2026-07-05

### Fixed - CRITICAL TeamInvitationService Session Method Bug

**Severity:** Critical (ALL team invitation endpoints blocked)

#### CRITICAL-4: TeamInvitationService Uses session.exec() on AsyncSession

**Fixed:** Replaced all `.exec()` calls with `.execute()` for SQLAlchemy AsyncSession compatibility.

**Issue:** TeamInvitationService used `.exec()` (SQLModel sync method) but routes inject raw SQLAlchemy AsyncSession which doesn't have .exec() method. This caused AttributeError on all team invitation endpoints.

**Affected Endpoints:**
- POST /api/team-invitations/ — Internal Server Error
- GET /api/team-invitations/me — Internal Server Error
- GET /api/team-invitations/team/{team_id} — Internal Server Error
- POST /api/team-invitations/{token}/accept — Internal Server Error
- POST /api/team-invitations/{token}/reject — Internal Server Error
- DELETE /api/team-invitations/{invitation_id} — Internal Server Error

**Error:**
```
AttributeError: 'AsyncSession' object has no attribute 'exec'
```

**Root Cause:**
- Routes inject: `AsyncSession` (via `Depends(get_session)`)
- Service expected: SQLModel Session with `.exec()` method
- AsyncSession only has `.execute()` method

**Changes:**
- Lines 190, 197, 210, 214, 218, 222, 228, 236, 246, 258: `.exec()` → `.execute()`
- Lines 193, 205: `.all()` → `.scalars().all()`
- All helper methods: `.scalar_one_or_none()` unchanged (compatible)

**Before:**
```python
result = await self.session.exec(select(TeamInvitation).where(...))
return list(result.all())
```

**After:**
```python
result = await self.session.execute(select(TeamInvitation).where(...))
return list(result.scalars().all())
```

### Files Modified

- `swx_core/services/team_invitation_service.py` - Fixed all .exec() calls to use .execute()

### Migration Required

None - this is a code bug fix, not a schema change.

### Breaking Changes

None - all changes are internal implementation fixes.

---

## [2.7.38] - 2026-07-05

### Fixed - Critical Schema and API Bugs

**Severity:** Critical (3 schema fixes, 1 API bug fix)

#### CRITICAL-1: Team Model Missing Columns (Migration Fix)

**Fixed:** Added migration for missing `swx_team` columns required by model.

**Issue:** v2.7.37 Team model expected `owner_id`, `created_at`, `updated_at` columns that didn't exist in database.

**Resolution:**
- v2_7_22_schema_changes.py migration already exists (adds columns + FK cascades)
- Verified migration is correct and complete
- Created migration guide for FastPII team

**Migration adds:**
- `swx_team.owner_id` (UUID, nullable, FK → swx_users.id ON DELETE SET NULL)
- `swx_team.created_at` (TIMESTAMP, default NOW())
- `swx_team.updated_at` (TIMESTAMP, default NOW())
- FK cascade updates on swx_user_role, swx_team_member, swx_users, etc.

#### CRITICAL-2: TeamMember Missing Columns (NEW Migration)

**Fixed:** Created v2_7_38_team_member_timestamps.py migration.

**Issue:** TeamMember model expected `created_at` and `updated_at` columns that didn't exist in database.

**Resolution:**
- Created new migration: v2_7_38_team_member_timestamps.py
- Adds `swx_team_member.created_at` (TIMESTAMP, default NOW())
- Adds `swx_team_member.updated_at` (TIMESTAMP, default NOW())
- UniqueConstraint(team_id, user_id) already in v2_7_24 migration

**Migration:**
```python
# v2_7_38_team_member_timestamps.py
def upgrade() -> None:
    op.add_column("swx_team_member", sa.Column("created_at", ...))
    op.add_column("swx_team_member", sa.Column("updated_at", ...))
```

#### CRITICAL-3: API Field Name Bug

**Fixed:** `role_id` → `team_role_id` in team member endpoints.

**Issue:** TeamMemberPublic responses returned `role_id` (legacy system role) instead of `team_role_id` (team-scoped role).

**Before:**
```python
# team_route.py line 225
return [TeamMemberPublic(id=m.id, ..., role_id=m.role_id) for m in members]

# team_controller.py line 27
return TeamMemberPublic(id=member.id, ..., role_id=member.role_id)
```

**After:**
```python
# team_route.py line 225
return [TeamMemberPublic(
    id=m.id,
    team_id=m.team_id,
    user_id=m.user_id,
    team_role_id=m.team_role_id,
    created_at=m.created_at,
) for m in members]

# team_controller.py line 27
return TeamMemberPublic(
    id=member.id,
    team_id=member.team_id,
    user_id=member.user_id,
    team_role_id=member.team_role_id,
    created_at=member.created_at,
)
```

**Impact:**
- ✅ Correct field name (`team_role_id`)
- ✅ Added missing `created_at` field
- ✅ Breaking change: clients must update to use `team_role_id`

#### MEDIUM-1: Model Exports (Already Fixed)

**Status:** ✅ Already fixed in v2.7.37

All models properly exported in `swx_core/models/__init__.py`:
- TeamRole, TeamRoleCreate, TeamRoleUpdate, TeamRolePublic, DEFAULT_TEAM_ROLES
- TeamInvitation, TeamInvitationCreate, TeamInvitationPublic, InvitationStatus
- TeamMemberUpdate

**Usage:**
```python
from swx_core.models import TeamRole, TeamInvitation, TeamMemberUpdate
```

### Files Modified

- `swx_core/database/migrations/v2_7_38_team_member_timestamps.py` - NEW: TeamMember timestamp columns
- `swx_core/routes/admin/team_route.py` - Fixed role_id → team_role_id
- `swx_core/controllers/team_controller.py` - Fixed role_id → team_role_id
- `MIGRATION_GUIDE_v2.7.38.md` - NEW: Comprehensive migration guide

### Migration Chain

**Required Order:**
```
v2_7_22_schema_changes.py          # Team columns + FK cascades
    ↓
v2_7_24_team_member_unique.py      # TeamMember unique constraint
    ↓
v2_7_38_team_member_timestamps.py  # TeamMember timestamps
```

**Apply Migrations:**
```bash
alembic upgrade head
```

### Breaking Changes

**API Response Field Change:**
- `TeamMemberPublic.role_id` → `TeamMemberPublic.team_role_id`
- Clients must update to use `team_role_id` field
- Added `created_at` field to responses

**Database Schema:**
- New non-nullable columns with default values (safe migration)
- No data loss or transformation required
- Existing rows get `NOW()` as default timestamps

### Documentation

**Added:** `MIGRATION_GUIDE_v2.7.38.md` with:
- Complete migration chain
- Verification SQL queries
- Rollback procedures
- Breaking change details

### For FastPII Team

**Action Required:**
1. Upgrade to v2.7.38
2. Apply migrations in order:
   ```bash
   alembic upgrade v2_7_22_schema_changes
   alembic upgrade v2_7_24_team_member_unique
   alembic upgrade v2_7_38_team_member_timestamps
   ```
3. Update API clients to use `team_role_id` instead of `role_id`
4. See `MIGRATION_GUIDE_v2.7.38.md` for detailed instructions

## [2.7.37] - 2026-07-02

### Added - Rate Limiting & CSRF Implementation

**Severity:** High (2 security enhancements implemented)

#### Rate Limiting Implementation

**Added:** Built-in rate limiting for all authentication endpoints using `@rate_limit_by_ip` decorator.

**Protected Endpoints:**
| Endpoint | Rate Limit | Window | Action |
|----------|-----------|--------|--------|
| `/auth/login` | 5 requests | 1 minute | `login` |
| `/auth/register` | 3 requests | 1 hour | `register` |
| `/auth/password/recover/{email}` | 3 requests | 1 hour | `password_recover` |
| `/auth/cookie/login` | 5 requests | 1 minute | `cookie_login` |
| `/auth/cookie/refresh` | 10 requests | 1 minute | `cookie_refresh` |

**Implementation:**
- Applied `@rate_limit_by_ip` decorator to all auth endpoints
- Uses existing Redis-backed rate limiting middleware
- Configuration via settings: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_LOGIN_MAX`, etc.
- Protects against brute force, account spam, SMTP abuse

**Configuration:**
```python
# settings.py
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_LOGIN_MAX: int = 5           # 5 req/min
RATE_LIMIT_REGISTER_MAX: int = 3        # 3 req/hour
RATE_LIMIT_PASSWORD_RECOVER_MAX: int = 3  # 3 req/hour
RATE_LIMIT_COOKIE_AUTH_MAX: int = 5    # 5 req/min
```

#### CSRF Protection Implementation

**Added:** CSRF middleware for cookie-based authentication using Double Submit Cookie pattern.

**Implementation:**
- Created `swx_core/middleware/csrf_middleware.py`
- Token stored in cookie (httpOnly=False, readable by JS)
- Token validated against `X-CSRF-Token` header
- Protects POST, PUT, PATCH, DELETE methods
- Exempt paths for health checks, metrics, public APIs

**Configuration:**
```python
# settings.py
CSRF_ENABLED: bool = True
CSRF_TOKEN_LENGTH: int = 32
CSRF_COOKIE_NAME: str = "csrf_token"
CSRF_HEADER_NAME: str = "X-CSRF-Token"
CSRF_COOKIE_MAX_AGE: int = 86400  # 24 hours
```

**CSRF Token Flow:**
1. Backend generates CSRF token, sets in cookie
2. Frontend reads token from cookie
3. Frontend includes token in `X-CSRF-Token` header
4. Backend validates token matches
5. State-changing requests protected

**Middleware Registration (Required):**
```python
from swx_core.middleware.csrf_middleware import CSRFMiddleware

app.add_middleware(
    CSRFMiddleware,
    cookie_name="csrf_token",
    header_name="X-CSRF-Token",
)
```

### Fixed - Type Safety

**Fixed:** Type annotation issues in settings and CSRF middleware:
- Fixed `all_cors_origins` type handling for `str | list[str]`
- Added proper generic type hints for `set[str]` and `list[str]`
- Improved code clarity

### Files Modified

- `swx_core/routes/access/auth_route.py` - Added rate limit decorators to auth endpoints
- `swx_core/middleware/csrf_middleware.py` - NEW: CSRF protection middleware
- `swx_core/config/settings.py` - Added CSRF and rate limit configuration, fixed type handling
- `docs/05-security/SECURITY_BEST_PRACTICES.md` - Updated with implementation details

### Migration Guide

**No migration required** - all changes are backward compatible.

**Recommended Actions:**
1. ✅ Upgrade to v2.7.37 for rate limiting and CSRF protection
2. ✅ Register CSRF middleware in your application (if using cookie-based auth)
3. ✅ Configure rate limits via environment variables (optional, defaults provided)
4. ✅ Update frontend to include CSRF token in request headers

## [2.7.36] - 2026-07-02

### Fixed - CRITICAL Security Vulnerabilities (FastPII Security Report)

**Severity:** Critical (1), High (2), Medium (2), Low (1)

#### Bug 1: CRITICAL - Cookie Login Token Leak

**Fixed:** `/auth/cookie/login` endpoint was returning access_token in response body, defeating httpOnly cookie security.

**Impact:**
- Access tokens were XSS-extractable from response body
- httpOnly cookies provided zero protection when same token available in JSON
- Frontend apps could accidentally store token in localStorage

**Fix:**
- Removed `access_token` and `token_type` from cookie_login response
- Response now returns only `{"email": "...", "message": "Authentication successful"}`
- Tokens accessible ONLY via httpOnly cookies (proper BFF pattern)

**Security Posture:**
| Before | After |
|--------|-------|
| Token in response body + cookie | Token ONLY in httpOnly cookie |
| XSS-extractable | XSS-resistant |
| Frontend can store in localStorage | Frontend MUST use cookies |

#### Bug 4: MEDIUM - Exception Handler Information Disclosure

**Fixed:** Generic exception handler was logging full exception strings including potentially sensitive data.

**Impact:**
- Database connection strings in logs
- File paths from IOError
- Internal service URLs from ConnectionError
- PII from custom exception messages

**Fix:**
- Changed to structured logging with `exc_type`, `path`, `request_id`
- Response includes `request_id` for debugging
- Uses `exc_info=True` for structured log aggregation systems
- No sensitive data in logs or responses

#### Bug 5: MEDIUM - Validation Error Handler Strips Details

**Fixed:** Validation errors returned generic message with no field details.

**Impact:**
- API consumers couldn't debug validation failures
- Increased support burden
- Poor developer experience

**Fix:**
- Returns structured validation errors: `{"detail": [...], "body": ...}`
- Field-level error details help consumers fix issues
- Uses WARNING level (appropriate for client errors)
- Standard FastAPI pattern (expected by clients)

#### Documentation: Rate Limiting & CSRF Protection

**Added:** Comprehensive security guidance in `docs/05-security/SECURITY_BEST_PRACTICES.md`

**Rate Limiting:**
- ⚠️ **swx-core does NOT include built-in rate limiting**
- Documented infrastructure-level implementations (Nginx, Redis)
- Provided application-level examples (slowapi)
- Listed recommended rate limits for auth endpoints

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 5 requests | 1 minute |
| `/auth/register` | 3 requests | 1 hour |
| `/auth/password/recover` | 3 requests | 1 hour |
| `/auth/cookie/login` | 5 requests | 1 minute |

**CSRF Protection:**
- Documented SameSite=Lax default protection
- Explained CSRF token implementation patterns
- Warned about SameSite=None configuration risks
- Provided production security best practices

### Files Modified

- `swx_core/routes/access/auth_route.py` - Removed token from cookie_login response
- `swx_core/main.py` - Fixed exception and validation handlers
- `docs/05-security/SECURITY_BEST_PRACTICES.md` - Added rate limiting and CSRF guidance

### Migration Guide

**No migration required** - all changes are backward compatible.

**Recommended Actions:**
1. ✅ Upgrade to v2.7.36 immediately (critical security fix)
2. ✅ Implement rate limiting at infrastructure or application level
3. ✅ Review CSRF protection if using cookie-based auth
4. ✅ Update frontend to NOT expect `access_token` in cookie_login response

**Frontend Changes:**
```javascript
// ❌ Before: Token in response (INSECURE)
const { access_token } = await response.json();

// ✅ After: Token ONLY in cookie (SECURE)
const { email, message } = await response.json();
// Token automatically sent via httpOnly cookie
```

### Security Acknowledgments

Thanks to the FastPII Security Team for the responsible disclosure.

## [2.7.35] - 2026-07-02

### Fixed - CRITICAL: OAuth registration skips user.created event

**Severity:** High  
**Impact:** Social auth users received no billing, profile, PII policy, onboarding, notifications, or email verification.

**Root Cause:**  
OAuth registration called `create_social_user()` at repository layer directly, bypassing `register_user_service()` — the only place where `user.created` event is emitted.

**What Was Skipped:**
- NotificationListener (welcome notification)
- UserCreatedBillingListener (billing setup, profile, PII policy, onboarding)
- UserCreatedAuditListener (audit log)
- All custom `user.created` event listeners

**Fix:**
Extended `register_user_service()` to support social auth parameters:
- Added `auth_provider` parameter (defaults to `"local"`)
- Added `provider_id` parameter for provider-specific user IDs
- Updated OAuth routes (Google, Facebook, custom) to use `register_user_service()`
- Ensures all lifecycle hooks and events fire for social auth users

**Changes:**
- `swx_core/services/auth_service.py`: Added `auth_provider` and `provider_id` params
- `swx_core/routes/access/oauth_route.py`: Replaced `create_social_user()` with `register_user_service()`
- `swx_core/repositories/user_repository.py`: Added type annotations
- `docs/04-core-concepts/OAUTH_PROVIDERS.md`: Documented event emission

**Breaking Changes:** None  
- Parameters have sensible defaults
- Existing email/password registration unchanged
- `create_social_user()` kept for backward compatibility

**Event Flow:**
```python
# Before: No events
OAuth → create_social_user() → database INSERT

# After: Full lifecycle
OAuth → register_user_service()
       → pre_register_hook
       → create_user (with auth_provider/provider_id)
       → post_register_hook
       → emit user.created
       → all listeners fire
```

**Migration:** None required. All OAuth registrations now emit `user.created` event.

## [2.7.34] - 2026-07-01

### Added - HTTP-only Cookie Authentication (BFF Pattern)

Extended cookie-based authentication support for all auth flows, enabling XSS-resistant browser authentication.

#### Cookie Authentication for All Flows

- **Dual authentication support** - Authorization header AND HTTP-only cookies work simultaneously
- **Priority-based extraction** - Header first, cookie fallback for maximum compatibility
- **New authentication scheme** - `BearerOrCookieAuth` class extracts JWT from both sources
- **Backward compatible** - Existing Authorization header auth continues to work unchanged

#### New Endpoints

- `GET /api/auth/me` - Check current authentication state (works with cookies)
- `POST /api/auth/cookie/login` - Email/password login with HTTP-only cookies
- `POST /api/auth/cookie/refresh` - Token refresh using HTTP-only cookie
- `POST /api/auth/cookie/logout` - Clear auth cookies (added in v2.7.33, now documented)

#### Security Benefits

| Before | After |
|--------|-------|
| localStorage tokens (XSS vulnerable) | HTTP-only cookies (XSS resistant) |
| Manual token attachment | Automatic cookie inclusion |
| Client-side token management | Server-side cookie management |
| No CSRF protection | SameSite attribute protection |

#### Configuration

Same cookie settings introduced in v2.7.33 OAuth BFF pattern:
- `COOKIE_ACCESS_TOKEN_NAME` (default: `swx_access_token`)
- `COOKIE_REFRESH_TOKEN_NAME` (default: `swx_refresh_token`)
- `COOKIE_SECURE` (auto-adjusts for local dev)
- `COOKIE_SAMESITE` (default: `lax`)
- `COOKIE_DOMAIN` (optional)

#### Frontend Integration

```javascript
// Login with cookies
await fetch('/api/auth/cookie/login', {
  method: 'POST',
  body: `username=${email}&password=${password}`,
  credentials: 'include'
})

// Check auth state
const user = await fetch('/api/auth/me', {
  credentials: 'include'
}).then(r => r.json())

// All requests include cookies automatically
await fetch('/api/user/profile', {
  credentials: 'include'
})
```

#### Changes

- **New file**: `swx_core/auth/core/bearer_or_cookie.py` - Authentication scheme
- **Updated**: `swx_core/auth/user/dependencies.py` - Uses `BearerOrCookieAuth`
- **Updated**: `swx_core/auth/admin/dependencies.py` - Uses `BearerOrCookieAuth`
- **Updated**: `swx_core/routes/access/auth_route.py` - Added cookie endpoints

#### Documentation

- **Updated**: `docs/04-core-concepts/AUTHENTICATION.md` - Added comprehensive cookie authentication section with:
  - Cookie-based authentication overview
  - Frontend integration examples
  - Migration guide from header to cookie auth
  - Security considerations
  - Endpoint reference

### Migration from v2.7.33

No migration required. The new cookie authentication is additive and fully backward compatible with existing Authorization header authentication.

## [2.7.33] - 2026-07-01

### Added - OAuth 2.0 Security Overhaul (BFF Pattern + PKCE)

Major security upgrade for OAuth authentication following RFC 9700 best practices.

#### PKCE Support (RFC 7636)

- **All OAuth flows now use PKCE** - Mandatory per RFC 9700 for all clients
- **S256 challenge method** - SHA-256 based code challenge (never 'plain')
- **Session-stored verifier** - PKCE verifier stored in server-side session
- **Applies to**: Google, Facebook, and all custom OAuth providers

#### Backend-for-Frontend (BFF) Pattern

- **HTTP-only cookies for tokens** - XSS-resistant token storage
- **No tokens in response body** - Callbacks redirect to frontend with cookies
- **Automatic token rotation** - Fresh tokens set on each OAuth login
- **Cookie configuration settings**:
  - `COOKIE_ACCESS_TOKEN_NAME` (default: `swx_access_token`)
  - `COOKIE_REFRESH_TOKEN_NAME` (default: `swx_refresh_token`)
  - `COOKIE_SECURE` (auto-adjusts for local dev)
  - `COOKIE_SAMESITE` (default: `lax`)
  - `COOKIE_DOMAIN` (optional)

#### New Endpoints

- `POST /api/auth/cookie/logout` - Clears HTTP-only auth cookies

#### Events

- **`user.login.social` event** - Emitted on social login with payload:
  ```json
  {
    "email": "user@example.com",
    "user_id": "uuid",
    "provider": "google",
    "is_new_user": false
  }
  ```

### Changed

- **OAuth callbacks now redirect** - Instead of returning JSON tokens, callbacks redirect to `{FRONTEND_HOST}/auth/callback`
- **Error handling via redirect** - OAuth errors redirect with `?error=...` parameter
- **Refactored oauth_route.py** - Extracted common logic into helper functions:
  - `generate_pkce_verifier()` / `generate_pkce_challenge()`
  - `validate_oauth_state()` - CSRF protection
  - `store_pkce_session()` / `clear_oauth_session()`
  - `set_auth_cookies()` - HTTP-only cookie management
  - `complete_oauth_login()` - Shared login completion logic

### Security Improvements

| Before | After |
|--------|-------|
| Tokens in JSON response | Tokens in HTTP-only cookies |
| No PKCE | PKCE mandatory (S256) |
| XSS vulnerable (localStorage) | XSS resistant (httpOnly) |
| Manual token management | Automatic via cookies |

### Migration Guide

#### Frontend Changes Required

1. **Remove localStorage token management** - Cookies are automatic
2. **Add `credentials: 'include'`** to all API requests:
   ```javascript
   fetch('/api/user/profile', {
     credentials: 'include'  // Send cookies automatically
   })
   ```
3. **Update OAuth callback handling**:
   - Old: Parse tokens from URL or response body
   - New: Just redirect to dashboard, cookies already set
4. **Use `/api/auth/cookie/logout`** for logout (clears cookies)

#### Environment Variables

```bash
FRONTEND_HOST=http://localhost:3003  # Required for redirects
COOKIE_SECURE=true                    # False for local dev
COOKIE_SAMESITE=lax                   # or 'strict' for stricter CSRF
```

### Documentation

- Updated `docs/04-core-concepts/AUTHENTICATION.md` - BFF pattern docs
- Updated `docs/04-core-concepts/OAUTH_PROVIDERS.md` - PKCE and redirect flow

## [2.7.32] - 2026-07-01

### Fixed - CRITICAL: Timezone-aware datetime database incompatibility

Massive fix for datetime timezone issues causing asyncpg `DataError: can't subtract offset-naive and offset-aware datetimes`.

**Root Cause**: PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` columns received timezone-aware `datetime.now(timezone.utc)` objects, causing asyncpg to fail when comparing/inserting datetimes.

**Solution**: All datetime objects passed to database columns now use `.replace(tzinfo=None)` to create naive UTC datetimes.

### Changed Files (60+ locations):

**Models (default_factory fixes):**
- `swx_core/utils/mixins.py` - TimestampMixin.created_at, updated_at, SoftDeleteMixin.soft_delete()
- `swx_core/models/billing.py` - All 11 timestamp fields (BillingAccount, Feature, Plan, PlanEntitlement, Subscription, UsageRecord)
- `swx_core/models/team_member.py` - created_at, updated_at
- `swx_core/models/team_role.py` - created_at, updated_at
- `swx_core/models/team_invitation.py` - created_at, updated_at, expires_at
- `swx_core/models/team.py` - created_at, updated_at
- `swx_core/models/admin_user.py` - created_at
- `swx_core/models/policy.py` - created_at, updated_at
- `swx_core/models/refresh_token.py` - created_at (already fixed in 2.7.31)
- `swx_core/utils/response.py` - 7 response model timestamp fields
- `swx_core/events/typed_event.py` - timestamp field
- `swx_core/events/dispatcher.py` - Event.timestamp field
- `swx_core/contracts/events.py` - EventInterface.timestamp field
- `swx_core/utils/health.py` - HealthCheckResult.timestamp field + business logic
- `swx_core/services/channels/models.py` - Alert.timestamp field
- `swx_core/cli/commands/resource_templates.py` - Generated model timestamps

**Services (business logic fixes):**
- `swx_core/services/job/job_runner.py` - completed_at, scheduled_at assignments (already had _utc_now_naive() fix)
- `swx_core/services/billing/subscription_service.py` - 5 timestamp assignments
- `swx_core/services/team_invitation_service.py` - accepted_at, rejected_at, created_at assignments
- `swx_core/services/rate_limit/rate_limiter.py` - reset_at assignments
- `swx_core/services/job/handlers.py` - subscription.ended_at assignments
- `swx_core/services/settings_service.py` - cache timestamp assignments
- `swx_core/services/job/job_dispatcher.py` - completed_at assignment
- `swx_core/services/settings_crud_service.py` - updated_at assignment
- `swx_core/services/policy/dependencies.py` - event timestamp assignment

**Repositories:**
- `swx_core/repositories/base.py` - 5 created_at/updated_at assignments
- `swx_core/repositories/tenant_aware.py` - updated_at assignment

**Security:**
- `swx_core/security/token_blacklist.py` - internal dict timestamp

**FastPII App (user application):**
- `apps/backend/api/swx_app/models/detection.py` - created_at, updated_at
- `apps/backend/api/swx_app/models/api_key.py` - created_at, updated_at

### Impact

This fix resolves ALL datetime insertion failures in applications using swx-core with PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` columns (the default).

## [2.7.31] - 2026-07-01

### Fixed
- **RefreshToken created_at timezone mismatch** — `created_at` field was using timezone-aware
  datetime (`datetime.now(timezone.utc)`) but the database column is `TIMESTAMP WITHOUT TIME ZONE`,
  causing asyncpg errors during OAuth callback. Now correctly uses naive datetime with
  `.replace(tzinfo=None)`.

## [2.7.30] - 2026-07-01

### Fixed
- **OAuth routes missing error logging** — Exceptions in OAuth login/callback handlers were silently
  swallowed without logging, making OAuth failures impossible to debug. Now all OAuth routes log
  exceptions with full traceback before raising HTTPException.

### Changed
- All OAuth exception handlers now re-raise `HTTPException` directly (prevents double-wrapping)
- Added `logger` to oauth_route.py with error logging on all exception paths

## [2.7.29] - 2026-07-01

### Fixed
- **Job runner datetime mismatch** — `_utc_now_naive()` was returning timezone-aware datetime
  instead of naive, causing asyncpg errors when comparing with `TIMESTAMP WITHOUT TIME ZONE`
  columns. Now correctly returns naive datetime with `.replace(tzinfo=None)`.

## [2.7.28] - 2026-06-30

### Fixed - Bug #7/29: Users Forced to Belong to a Team

- **Auto-create personal team on registration** — New users now get a personal team with `tenant_id` set automatically
- **`AUTO_CREATE_PERSONAL_TEAM` setting** — Default `True`, creates personal team and assigns `owner` role
- **No more 500 errors** — Users without `tenant_id` no longer crash tenant-aware endpoints

### Added

- `create_personal_team()` hook — Creates team `{user}'s Team` and sets `user.tenant_id`
- `AUTO_CREATE_PERSONAL_TEAM` setting — Controls automatic team creation (default: True)
- Migration `v2_7_27_personal_team_backfill.py` — Backfills existing users without tenant_id

### Fixed - Bug #14: Alembic Migration Rollback Handling

- All migrations now have proper `downgrade()` functions
- Migration `v2_7_27_personal_team_backfill.py` includes rollback support

### Added - FR1: Extensibility for Custom Social Auth Providers

- **OAuth Provider Registry** — `swx_core.core.oauth_providers` module
- **Configuration-based providers** — Add GitHub, LinkedIn, Apple, etc. via `.env`
- **Dynamic provider loading** — No code changes needed to add new providers

#### Usage:

```bash
# .env
OAUTH_PROVIDERS=github,linkedin

GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=http://localhost:8001/api/oauth/github/callback
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user
GITHUB_SCOPE=user:email

LINKEDIN_CLIENT_ID=xxx
LINKEDIN_CLIENT_SECRET=xxx
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/oauth/linkedin/callback
LINKEDIN_AUTH_URL=https://www.linkedin.com/oauth/v2/authorization
LINKEDIN_TOKEN_URL=https://www.linkedin.com/oauth/v2/accessToken
LINKEDIN_USER_INFO_URL=https://api.linkedin.com/v2/me
LINKEDIN_SCOPE=r_emailaddress r_liteprofile
```

### Documentation

- New `docs/04-core-concepts/OAUTH_PROVIDERS.md` — OAuth extensibility guide
- Updated `docs/04-core-concepts/REGISTRATION_HOOKS.md` — Added personal team hook docs

## [2.7.27] - 2026-06-30

### Added - Bug #25: Separate Team Roles from System RBAC

- **TeamRole model** — New model for team-scoped roles (owner, editor, viewer) separate from system RBAC
- **TeamPermissionChecker service** — Check team-scoped permissions based on TeamRole.permissions dict
- **DEFAULT_TEAM_ROLES** — Seeded roles: owner (full control), editor (can edit), viewer (read-only)
- **Migration v2_7_26** — Creates swx_team_role table and migrates TeamMember.role_id to team_role_id

### Changed - Bug #25

- **TeamMember.team_role_id** — Now uses team_role_id (FK to swx_team_role) instead of role_id (FK to swx_role)
- **TeamMemberCreate** — Uses team_role_id instead of role_id
- **TeamMemberUpdate** — New schema for updating team role
- **team_service.py** — Updated to use TeamRole instead of system Role

### Added - Bug #26: Team Invitation System

- **TeamInvitation model** — Invitation with status (pending, accepted, rejected, expired, revoked)
- **TeamInvitationService** — Full CRUD: create, accept, reject, revoke with permission checks
- **TeamInvitation routes** — API endpoints: POST /, POST /{token}/accept, POST /{token}/reject, DELETE /{id}
- **7-day expiration** — Invitations expire after 7 days by default
- **Secure tokens** — 64-character random tokens for invitation acceptance

### New Models

- `swx_team_role` — Team-scoped roles with permissions dict
- `swx_team_invitation` — Team invitations with audit trail

### New Services

- `TeamPermissionChecker` — Check team-scoped permissions
- `TeamInvitationService` — Manage invitation lifecycle

### New Routes

- `/team-invitations/` — Create invitation
- `/team-invitations/{token}/accept` — Accept invitation
- `/team-invitations/{token}/reject` — Reject invitation
- `/team-invitations/{id}` (DELETE) — Revoke invitation
- `/team-invitations/team/{team_id}` — List team invitations
- `/team-invitations/me` — List my invitations

## [2.7.25] - 2026-06-30

### Fixed
- **Bug 16: Invalid UUID headers silently ignored** — `X-Tenant-ID` and `X-Team-ID` headers with
  invalid UUIDs were silently dropped. Now logs a warning for debugging.
- **Bug 17: Hardcoded log directory** — Log file path was hardcoded to `"logs/swx_core.log"`.
  Added `LOG_DIR` setting (default: `"logs"`) for configurable log directory.
- **Bug 21: Expired subscriptions granted access** — `get_entitlement()` checked subscription status
  but not `current_period_end`. Now requires `current_period_end >= now()` to grant entitlements.
- **Bug 23: Duplicate team membership allowed** — `TeamMember` lacked composite unique constraint,
  allowing same user to be added to same team multiple times. Added `UniqueConstraint("team_id", "user_id")`.

### Added
- `LOG_DIR` setting for configurable log directory path.
- Migration `v2_7_24_add_team_member_unique.py` for TeamMember unique constraint.

### Changed
- `TeamMember.__table_args__` now includes `UniqueConstraint("team_id", "user_id")`.

## [2.7.23] - 2026-06-29

### Added
- **Default role assignment on registration** — New `AUTO_ASSIGN_DEFAULT_ROLE` (default: `True`) and
  `DEFAULT_USER_ROLE` (default: `"user"`) settings. When enabled, newly registered users automatically
  receive the specified role via a post-registration hook. Requires `seed_system.py` to have created
  the role.
- **Billing account creation on registration** — New `AUTO_CREATE_BILLING_ACCOUNT` (default: `True`)
  setting. When enabled (and `BILLING_ENABLED=True`), a USER billing account and free-tier subscription
  are created automatically for newly registered users.
- **Multi-hook registration system** — `RegistrationHookRegistry` now supports multiple post-register
  hooks via `add_post_register()`. `set_post_register()` still works but replaces all hooks. Both
  default hooks (role assignment, billing) are registered via `add_post_register()`.
- **`swx_core/core/default_hooks.py`** — New module with `assign_default_role()` and
  `create_billing_account()` post-registration hooks.
- **`_register_default_hooks()` in bootstrap** — Automatically registers default hooks based on settings
  during `bootstrap_app()` (Phase 2.5).
- **Alembic migration template** — `swx_core/database/migrations/v2_7_22_schema_changes.py` covering
  all v2.7.22 schema changes (new columns on `swx_team`, `billing_interval` on `swx_billing_plan`,
  FK `ondelete` clauses on 17 foreign keys).

### Changed
- `RegistrationHookRegistry._post_hook` changed from single hook to `_post_hooks: List[PostRegisterHook]`.
- `registration_hooks.post_register` property now returns a combined coroutine that runs all hooks
  sequentially, catching and logging exceptions per hook.

## [2.7.22] - 2026-06-29

### Fixed - CRITICAL
- **Bug 8: Un awaited `get_password_hash()` in `user_repository.py`** — `hashed_password = get_password_hash(password)`
  was called without `await`, silently returning a coroutine object instead of a hash.
- **Bug 1: No session injection in BaseRepository** — Added optional `session` parameter to
  `BaseRepository.__init__()` and `_session_context()` async context manager. Callers can now
  inject a session for Unit of Work / multi-operation transactions. Without a session, behavior
  is unchanged (auto-created per-operation session).

### Fixed - HIGH
- **Bug 12: Tenant filter leak** — `_apply_tenant_filter()` in `tenant_aware.py` returned the
  unfiltered query when no tenant context was available, exposing all records. Now returns
  `query.where(sa_false())` (no rows) instead.
- **Bug 10: Insecure CORS defaults** — `setup_cors_middleware()` defaulted to `allow_origins=["*"]`
  with `allow_credentials=True`, which browsers reject and is insecure. Changed default to
  `allow_origins=[]` with `allow_credentials=False`; credentials enabled only when origins
  are explicitly configured.
- **Bug 9: Rate-limit skip paths too broad** — Removed `/api/admin/`, `/api/auth`,
  `/api/user/profile`, `/api/qa_article`, `/api/oauth` from skip_paths. Only health/docs
  endpoints remain unrate-limited.
- **Bug 20: Subscription race condition** — Added `.with_for_update()` to the active-subscription
  SELECT in `subscription_service.py`, preventing concurrent subscription creation under load.
- **Bug 28: ValueError in subscription service** — Changed `raise ValueError(...)` to
  `raise HTTPException(status_code=404, ...)` in `SubscriptionService.create_subscription()`
  so invalid plan keys return a proper 404 instead of an unhandled 500.

### Fixed - MEDIUM
- **Bug 13: Inactive user password recovery** — Added `is_active` check in
  `recover_password_service()` — inactive users can no longer request password resets.
- **Bug 15: AlertEngine fire-and-forget with no error handling** — Added `_pending_tasks` set
  and `_handle_task_error` callback to `AlertEngine.emit()`. Unhandled task exceptions are now
  logged instead of silently swallowed.
- **Bug 5: Deprecated `datetime.utcnow()` across 51 call sites in 37 files** — Replaced all
  `datetime.utcnow()` calls with `datetime.now(timezone.utc)` and added `timezone` import
  where needed.
- **Bug 22: Foreign keys missing `ondelete`** — Added explicit `ondelete` clauses
  (`CASCADE`, `RESTRICT`, `SET NULL`) to all FK columns in `team_member`, `user`, `user_role`,
  `role_permission`, `billing`, `system_config`, and `team` models using
  `sa_column=Column(PG_UUID(...), ForeignKey(..., ondelete=...))`.

### Fixed - LOW
- **Bug 27: Hardcoded 30-day billing interval** — Added `BillingInterval` enum and
  `BILLING_INTERVAL_DAYS` dict to `billing.py`. Plan model now has a `billing_interval` field.
  `SubscriptionService.create_subscription()` uses `BILLING_INTERVAL_DAYS` instead of a
  hardcoded 30.
- **Bug 24: Team model missing owner and timestamps** — Added `owner_id` (FK to `swx_users.id`
  with `ondelete="SET NULL"`), `created_at`, and `updated_at` to `Team` model.
- **Bug 18: No billing account on team creation** — `create_team_service()` now creates a
  `TEAM` billing account via `SubscriptionService.get_or_create_account()`.
- **Bug 19: Orphan billing data on team deletion** — `delete_team_service()` now deletes
  related `UsageRecord`, `Subscription`, and `BillingAccount` rows before deleting the team.

### Changed
- `BaseRepository.__init__()` now accepts an optional `session: AsyncSession` parameter.
- `_session_context()` async context manager yields injected session or auto-creates one.
- All FK fields in models now use `sa_column=Column(PG_UUID(as_uuid=True), ForeignKey(..., ondelete=...))`
  instead of `Field(foreign_key=...)`.
- `tenant_aware.py`: `sa_false` import moved from inline to module-level.

## [2.7.21] - 2026-06-16

### Fixed - CRITICAL
- **v2.7.20 regression: routes not mounted (404)** - The v2.7.20 `hasattr(r, "path")`
  guard prevented the crash but silently skipped all `_IncludedRouter` objects,
  leaving `core_paths` empty. Since `set().issubset(...)` is always `True`,
  `app.include_router(core_router)` was never called and all endpoints returned 404.
  Replaced both inline comprehensions (lines 119 and 123) with a new
  `_extract_route_paths()` helper that recursively drills into
  `_IncludedRouter.original_router` to collect real path strings.

### Added
- **`_extract_route_paths()` helper** in `bootstrap.py` - Recursively extracts route
  paths from a router/app, handling both plain routes (`.path`) and FastAPI 0.115.0+
  `_IncludedRouter` wrappers (`.original_router`).

### Tests
- 8 new tests in `tests/bootstrap/test_bootstrap_routes.py` covering:
  - Plain route extraction
  - Nested `_IncludedRouter` recursive extraction
  - Deeply nested routers (3+ levels)
  - Empty router edge case
  - Full FastAPI app with included sub-routers
  - Core routes actually mounted on fresh app (v2.7.20 regression)
  - No double-registration on repeated `bootstrap_app` calls
  - `core_router` yields real paths (not empty)

## [2.7.20] - 2026-06-16

### Fixed - CRITICAL
- **`bootstrap_app()` crash on FastAPI 0.115.0+** - Fixed `AttributeError: '_IncludedRouter'
  object has no attribute 'path'` on line 123 of `bootstrap.py`. FastAPI 0.115.0+ wraps
  included sub-routers in `_IncludedRouter` objects that lack a `.path` attribute. Added
  the same `hasattr(r, "path")` guard that line 119 already had, safely skipping wrapper
  objects. Without this fix, the server crashes on every startup when using
  `include_router()` with FastAPI >= 0.115.0.

## [2.7.19] - 2026-05-29

### Fixed
- **Post-registration hook exception handling** - Hook failures no longer mask successful
  user creation with a 400 error. Post-hook exceptions are now caught and logged as
  warnings, and the `user.created` event is always emitted regardless of hook outcome.
  Previously, a failing post-hook would prevent the event from firing and return a 400
  error even though the user was successfully created.

## [2.7.18] - 2026-05-29

### Fixed - CRITICAL
- **Core routes not mounted** - Fixed `dynamic_import` returning package `__init__.py` modules
  alongside individual route files, causing double registration and 404 errors.
  Package modules in route directories are now skipped; only leaf route files are registered.
- **Auth route prefix doubling** - Fixed `/api/auth/auth/` double prefix caused by `__init__.py`
  aggregation routers being processed alongside individual route files.
- **Misleading "No core routes found" warning** - Fixed `for...else` bug in `router.py` that
  printed "No core routes found" even when routes were successfully loaded.

### Added
- **Registration Hook Registry** - `swx_core.core.hooks.registration_hooks` singleton for
  configuring pre/post registration hooks at app startup. The auth route endpoint now
  automatically uses registered hooks, solving the "hooks not exposed via HTTP API" issue.
- **Explicit tenant_id in TenantAwareRepository** - New `explicit_tenant_id` and `explicit_team_id`
  constructor parameters allow bypassing context vars for apps that pass tenant explicitly:
  ```python
  repo = TenantAwareRepository(Product, explicit_tenant_id="tenant-123")
  ```

### Changed
- **TenantAwareRepository** - `_apply_tenant_filter` now respects explicit tenant/team IDs over
  context vars. Super-admin bypass only applies when no explicit ID is set.
- **Auth controller** - `register_controller` now passes `registration_hooks.pre_register` and
  `registration_hooks.post_register` to `register_user_service`.

## [2.7.17] - 2026-05-29

### Added - Registration Extension Points
- **Lifecycle Hooks for Registration** - `register_user_service()` now accepts hook parameters:
  - `pre_register_hook` - Async function called BEFORE user creation for validation/tenant assignment
  - `post_register_hook` - Async function called AFTER user creation for organization setup/side effects
  - Hook execution order: pre → create → post → emit event → return user
  - Both hooks receive `event_context` for passing custom data
- **CORE_ROUTE_PREFIX Setting** - Configurable prefix for core framework routes:
  - Default: `""` (empty string) - core routes at `/api/auth`
  - Set to `"/v1"` for `/api/v1/auth` to match versioned app routes
  - Enables apps to mount core routes consistently with their API versioning

### New Documentation
- **Registration Hooks** - `docs/04-core-concepts/REGISTRATION_HOOKS.md`
  - Complete guide to registration extension points
  - Examples: multi-tenant registration, invitation-based signup, enterprise SSO
  - Comparison of hooks vs events vs service override approaches
- **Route Configuration** - `docs/02-getting-started/ROUTE_CONFIGURATION.md`
  - Route prefix configuration explained
  - Migration guide for swx_app compatibility
  - Troubleshooting common routing issues

### Changed
- **Router** - Core routes respect `CORE_ROUTE_PREFIX` setting for URL mounting
- **Settings** - Added `CORE_ROUTE_PREFIX` field with default empty string
- **GETTING_STARTED.md** - Added `CORE_ROUTE_PREFIX` to environment variables documentation

## [2.7.16] - 2026-05-29

### Added - Multi-Tenant Support
- **TenantAwareRepository** - Base repository with automatic tenant filtering via context variables
  - Automatically filters queries by `tenant_id` or `team_id` from request context
  - Supports super-admin bypass for accessing all tenants
  - Auto-injects tenant context on create operations
- **TenantContextMiddleware** - Middleware for extracting and setting tenant context
  - Extracts tenant from `X-Tenant-ID` header or authenticated user
  - Implements context cleanup in finally block to prevent leakage
  - Exempts auth and health endpoints
- **TenantAwareController** - Base controller with tenant context injection
  - Extends BaseController with automatic tenant data injection
  - Works with TenantAwareRepository for full tenant isolation
- **EntitlementService** - Service for quota enforcement and feature entitlements
  - `require_quota()` - Check if owner has remaining quota
  - `require_feature()` - Check access to boolean features
  - `QuotaExceededError` exception with feature/limit/current details
  - Dependency helpers: `require_quota_dependency()`, `require_feature_dependency()`
- **PostgreSQL RLS Support** - Row-Level Security integration
  - `swx_core/database/rls.py` - SQLAlchemy event listeners for RLS
  - `swx_core/database/migrations/rls_template.sql` - Migration template for enabling RLS

### Changed
- **User Model** - Added `tenant_id` field to `UserBase` for multi-tenant support
- **Auth Dependencies** - `get_current_user()` now sets tenant context for downstream use
- **Repositories** - Added `TenantAwareRepository` export to `__init__.py`
- **Controllers** - Added `TenantAwareController` export to `__init__.py`
- **Middleware** - Added `TenantContextMiddleware` export to `__init__.py`

### New Modules
- `swx_core/core/tenant.py` - ContextVar-based tenant context management
- `swx_core/core/__init__.py` - Core module exports
- `swx_core/repositories/tenant_aware.py` - TenantAwareRepository implementation
- `swx_core/controllers/tenant_aware.py` - TenantAwareController implementation
- `swx_core/middleware/tenant_middleware.py` - TenantContextMiddleware implementation
- `swx_core/services/billing/quota_service.py` - EntitlementService implementation

## [2.7.15] - 2026-05-29

### Fixed - CRITICAL
- **Routes Not Mounted** - Fixed routes not accessible despite being logged as registered
  - Root cause: `__init__.py` files in routes subdirectories only imported routers but didn't create module-level `router` variable
  - Fix: Added `router = APIRouter()` + `router.include_router()` aggregations in each `__init__.py`
  - Affected files: `swx_core/routes/access/__init__.py`, `swx_core/routes/admin/__init__.py`, `swx_core/routes/user/__init__.py`, `swx_core/routes/utils/__init__.py`
  - Impact: All routes from swx_core/routes/* now properly accessible

### Fixed
- **Router Prefix Handling** - Fixed v2.7.14 bug where router prefixes were incorrectly stripped
- **User Model Timestamps** - Added `created_at` and `updated_at` fields to User model
- **Timezone-Aware DateTime** - Fixed `datetime.now(timezone.utc)` causing PostgreSQL errors for TIMESTAMP WITHOUT TIME ZONE columns
  - Changed to `datetime.utcnow()` for naive datetime compatibility

### Documentation
- **Router Module Pattern** - Documented requirement for module-level `router` variable in route `__init__.py` files

## [2.7.8] - 2026-05-01

### Fixed - CRITICAL
- **Job Runner SQL Bug** - Fixed unqualified column reference `job.status` → `swx_job.status` in PostgreSQL query
  - Error: `missing FROM-clause entry for table "job"` in PostgreSQL
  - File: `swx_core/services/job/job_runner.py:202`
  - Fix: Changed `text("job.status = ANY(...)")` → `text("swx_job.status = ANY(...)")`
  - Impact: Background job processing was completely broken, workers spammed errors

### Fixed
- **get_current_user Export** - Added `get_current_user` and `UserDep` to `swx_core.auth.__init__.py`
  - Users can now: `from swx_core.auth import get_current_user`
  - Previously required workaround: `from swx_core.auth.user import get_current_user`

### Documentation
- **AdminUser Import Path** - Confirmed correct path: `from swx_core.models import AdminUser`
  - No `swx_core.models.admin` module exists - AdminUser is in `admin_user.py`

## [2.7.7] - 2026-05-01

### Fixed - CRITICAL
- **SyntaxError in ai_exports/graph.py** - Removed corrupt prefixes (#MY|, #NS|, etc.) causing unterminated string literal
- **SyntaxError in ai_exports/contracts.py** - Same corruption fix
- **swx CLI now works** - Fixed blocking import error

### Changed
- Removed autogenerate from `swx setup` to prevent issues with existing projects
- `swx setup` now provides manual instructions instead of auto-generating migrations
- Safer for projects with custom tables that reference core tables

### Bug Fixes
- ai_exports files no longer have corrupt line prefixes
- Existing projects with migrations can safely run `swx setup`

## [2.7.6] - 2026-05-01

### Fixed - Database Migration Auto-Generation
- **swx_job Table Not Created** - Setup command now auto-generates initial migration if none exist
  - `swx setup` detects empty migrations/versions/ directory
  - Automatically runs `alembic revision --autogenerate -m "initial"`
  - Creates all framework tables including `swx_job`, `swx_users`, `swx_role`, etc.
  
### Changed
- `_setup_database()` in `framework.py` now generates initial migration on fresh projects
- Users no longer need to manually run `swx db revision "initial"` first

## [2.7.5] - 2026-05-01

### Fixed - Import/Module Issues
- **Broken Import in CLI Framework** - Fixed `swx_core/cli/commands/framework.py:239` importing from non-existent `swx_core.database.core`. Changed to `swx_core.database.db`.
- **Database Module Exports** - Added exports to `swx_core/database/__init__.py` for cleaner imports:
  - `AsyncSessionLocal`, `SessionLocal` - session factories
  - `async_engine`, `engine` - database engines
  - `get_async_db`, `get_db`, `get_session` - dependency injectors
  - `SessionDep`, `SyncSessionDep` - type annotations

### Documentation
- Confirmed cache functions are correctly located at `swx_core.utils.cache` (not `swx_core.cache`)
- Confirmed BaseRepository is at `swx_core.repositories.base` (not `swx_core.repository`)

## [2.7.4] - 2026-04-29

### Fixed - CRITICAL
- **All Services: Local EventBus Instance Bug** - Fixed ALL services creating local `EventBus()` instances instead of using the global `event_bus` singleton. This affected:
  - `role_service.py` (5 occurrences)
  - `user_service.py` (3 occurrences)
  - `permission_service.py` (3 occurrences)
  - `team_service.py` (5 occurrences)
  - `user_role_service.py` (2 occurrences)
  - `policy_service.py` (3 occurrences)
  - `base.py` (BaseService class)
  
  **Impact**: ALL events emitted by these services were going to empty buses with NO registered listeners. Fix ensures all events go to the global singleton where listeners are registered.

### Changed
- All services now import and use `event_bus` singleton from `swx_core.events.dispatcher`
- BaseService now stores reference to global `event_bus` instead of creating new instance

## [2.7.3] - 2026-04-29

### Fixed - CRITICAL
- **user.created Event Not Emitted** - Fixed `register_user_service()` creating a local `EventBus()` instance instead of using the global `event_bus` singleton. Events are now emitted to the correct bus where listeners are registered.
- **Event Context Empty Dict Handling** - Changed `if event_context:` to `if event_context is not None:` to correctly handle empty dict.

### Added
- **Discovery Diagnostic Logging** - Added DEBUG-level logs explaining why Phase 3 listener registration might be skipped
- **diagnose_discovery() Function** - New helper to debug discovery configuration:
  ```python
  from swx_core.bootstrap import diagnose_discovery
  diagnose_discovery()  # Returns app_exists, has_listeners, phase_3_will_run
  ```

### Changed
- **Bootstrap Phase 3** - Now logs DEBUG message when skipping listener registration, showing which directory is missing

## [2.7.2] - 2026-04-29

### Added
- **Event Dispatch Logging** - INFO-level logging for event dispatch with listener count, execution times, and completion status
- **Listener Registration Logging** - INFO-level logging when listeners are registered with pattern, priority, and queueable details
- **Event Debug Utilities** - New `swx_core.events.debug` module with inspection tools:
  - `list_all_listeners()` - List all registered listeners grouped by event
  - `test_pattern()` - Test wildcard pattern matching
  - `trace_event()` - Trace which listeners receive an event
  - `print_event_bus_status()` - Print comprehensive event bus status
  - `get_listener_count()` - Count registered listeners
  - `verify_listener_registered()` - Verify a listener is registered
- **Example Listeners** - Template project includes example listener implementations in `swx_app/listeners/example_listeners.py`

### Changed
- **Listener registration logging** - Changed from DEBUG to INFO level for visibility
- **Event dispatch logging** - Added detailed timing and listener invocation logging

### Fixed
- **Listener visibility** - Listeners now log at INFO level when registered during bootstrap

### Documentation
- **Event System Guide** - Added troubleshooting section to `docs/04-core-concepts/EVENT_SYSTEM.md`
- **Debug utilities documentation** - Documented all debug utilities with examples
- **Pattern matching examples** - Added wildcard pattern examples and tests

## [2.7.1] - 2026-04-29

### Fixed
- **Critical: Event Hashability** - Fixed `unhashable type: 'Event'` bug by adding `__hash__` method to Event class
- **Critical: TypedEvent Hashability** - Added `__hash__` method to TypedEvent class for use in sets/dicts
- **Wildcard Pattern Matching** - Fixed bug where `user.*` pattern matched all events instead of only `user.created`, `user.deleted`, etc.
- **Event Context Handling** - Fixed empty dict `event_context={}` being treated as `None` (now correctly adds `"context": {}` to payload)

### Added
- **TypedEvent `__hash__` method** - TypedEvent objects can now be used in sets and as dict keys
- **ListenerRegistration.pattern field** - Stores pattern for wildcard listeners (supports `*`, `user.*`, `*.created`)
- **EventBus._matches_pattern()** - Pattern matching logic for wildcard event listeners
- **Comprehensive edge case tests** - 25 new tests for event emission edge cases

### Changed
- **Event context parameter** - Changed from `if event_context else` to `if event_context is not None else` across all services to correctly handle empty dict

## [2.7.0] - 2026-04-28

### Added
- **Comprehensive Event Emission**: All SwX services now emit domain events for CRUD operations
- **Event Context Parameter**: All service methods accept `event_context` parameter for additional metadata
- **Typed Event Base Classes**: New `TypedEvent` base class for type-safe event handling

### Services with Event Emission

#### Authentication & User Management
- **auth_service.py**: `register_user_service()` now emits `user.created` event
- **user_service.py**: 
  - `update_user_profile_service()` emits `user.updated` event
  - `update_password_service()` emits `user.password_changed` event
  - `delete_user_service()` emits `user.deleted` event

#### Role & Permission Management
- **role_service.py**:
  - `create_role_service()` emits `role.created` event
  - `update_role_service()` emits `role.updated` event
  - `delete_role_service()` emits `role.deleted` event
  - `assign_permission_to_role_service()` emits `role.permission_assigned` event
  - `remove_permission_from_role_service()` emits `role.permission_removed` event

- **permission_service.py**:
  - `create_permission_service()` emits `permission.created` event
  - `update_permission_service()` emits `permission.updated` event
  - `delete_permission_service()` emits `permission.deleted` event

#### Team Management
- **team_service.py**:
  - `create_team_service()` emits `team.created` event
  - `update_team_service()` emits `team.updated` event
  - `delete_team_service()` emits `team.deleted` event
  - `add_team_member_service()` emits `team.member_added` event
  - `remove_team_member_service()` emits `team.member_removed` event

#### User-Role Management
- **user_role_service.py**:
  - `assign_role_to_user_service()` emits `user_role.assigned` event
  - `remove_role_from_user_service()` emits `user_role.removed` event

#### Policy Management
- **policy_service.py**:
  - `create_policy_service()` emits `policy.created` event
  - `update_policy_service()` emits `policy.updated` event
  - `delete_policy_service()` emits `policy.deleted` event

### Event Payload Structure

All events follow a consistent payload structure:

```python
# Create/Update/Delete events
{
    "id": "uuid-string",
    "data": {"field": "value"},           # Resource data
    "context": {"key": "value"}            # Optional context
}

# Update events (additional fields)
{
    "id": "uuid-string",
    "old_values": {"field": "old_value"},
    "new_values": {"field": "new_value"},
    "context": {"key": "value"}            # Optional context
}
```

### Example Usage

```python
# User registration with context
user = await register_controller(
    session=session,
    user_in=user_create,
    request=request,
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# Role creation with context
role = await create_role_service(
    session=session,
    role_in=role_create,
    event_context={"created_by": admin_id},
)
```

### Tests
- **New Tests**: `tests/services/test_service_event_emissions.py` with comprehensive event tests
- **New Tests**: `tests/services/test_user_created_event.py` for user registration events
- **Coverage**: 23 tests covering all service event emissions

### Breaking Changes
- None - all changes are backward compatible

### Migration Guide
No migration required. Event emission is automatic. To receive additional context:

1. Pass `event_context` parameter to any service method:
   ```python
   await create_role_service(session, role_in, event_context={"created_by": user_id})
   ```

2. Listen for events using EventBus:
   ```python
   from swx_core.events import EventBus
   
   @EventBus.on("role.created")
   async def on_role_created(event):
       role_id = event.payload["id"]
       context = event.payload.get("context", {})
       created_by = context.get("created_by")
   ```

## [2.6.0] - 2026-04-28

### Added
- **Event Context Enhancement**: BaseService CRUD methods now accept `event_context` parameter for additional context in event payloads
- **before_emit Hook**: Async hook called before event emission to enhance payload with computed/async context
- **after_emit Hook**: Async hook called after event emission for side effects
- **Structured Event Payloads**: Events now support `{"id": ..., "data": ..., "context": ...}` structure

### Changed
- **BaseService.create()**: Added `event_context: Dict[str, Any] | None` parameter
- **BaseService.update()**: Added `event_context` parameter
- **BaseService.delete()**: Added `event_context` parameter
- **BaseService.soft_delete()**: Added `event_context` parameter
- **BaseService.restore()**: Added `event_context` parameter
- **BaseService.bulk_create()**: Added `event_context` parameter

### Example Usage
```python
# Before: Workaround with duplicate events
user = await user_service.create(data)
await event_bus.dispatch("user.created", payload={...context...})

# After: Single event with context
user = await user_service.create(
    data={"email": "user@example.com", "password": "secret"},
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# With before_emit hook for computed context
class UserService(BaseService[User]):
    async def before_emit(self, event_name, payload, instance):
        if event_name == "user.created" and instance:
            payload["context"] = {
                **payload.get("context", {}),
                "user_type": await self._determine_user_type(instance),
            }
        return payload
```

### Industrial Standard Compliance
- Follows Django Signals pattern (`sender + **kwargs`)
- Follows Flask/Blinker pattern (explicit context injection)
- Follows SQLAlchemy event hooks (before/after pattern)
- Follows production SaaS patterns (aden-hive/hive, ricequant/rqalpha)

### Tests
- **New Tests**: `tests/services/test_base_service_event_context.py` with 10 comprehensive tests
- **Coverage**: event_context propagation, before_emit/after_emit hooks, backward compatibility

## [2.5.0] - 2025-04-28

### Added
- **Event Listener Auto-Discovery**: Listeners in `swx_core/events/listeners/` and `swx_app/listeners/` are automatically discovered and registered during bootstrap
- **Listener Auto-Registration**: No manual EventServiceProvider registration needed - listeners self-register
- **Wildcard Pattern Support**: Listeners can use wildcard patterns like `user.*`, `emergency.*`, or `*` for all events
- **Priority-Based Execution**: Listeners execute in priority order (highest first)
- **Queueable Listeners**: Support for background queue processing with `queueable=True`
- **New Functions in `swx_core.events`**:
  - `discover_listeners(module)`: Find all Listener subclasses in a module
  - `register_listener(listener_class)`: Register a listener with EventBus
  - `load_listeners_from_path(base_path, package_name)`: Load listeners from directory
  - `load_all_listeners()`: Load and register all core and app listeners
- **New Module**: `swx_core/events/listener_loader.py` with auto-discovery implementation
- **New Directory**: `swx_core/events/listeners/` for core framework listeners
- **New Tests**: `tests/events/test_listener_loader.py` with comprehensive coverage
- **New Documentation**: `docs/04-core-concepts/EVENT_SYSTEM.md` with examples and best practices

### Fixed
- **Bootstrap Integration**: `register_event_listeners()` now properly called during bootstrap (Phase 3)
- **Import Exports**: All listener_loader functions now properly exported in `swx_core/events/__init__.py`
- **Path Handling**: Fixed `path_exists` issue in listener_loader using `Path.exists()` directly

### Changed
- **EventListener Pattern**: Now follows Laravel's EventServiceProvider pattern for auto-discovery
- **Bootstrap Phases**: Added Phase 3 for listener registration after provider boot

## [2.4.0] - 2025-04-27

### Added
- **Table Prefix**: All framework tables now use `swx_` prefix to differentiate core tables from user tables
- **Migration Support**: Migration script to rename existing tables with `swx_` prefix
- **Foreign Key Updates**: All 16 foreign key references updated to use prefixed table names

### Changed
- **Table Names**: 21 core tables renamed with `swx_` prefix
- **Raw SQL**: Updated 5 raw SQL queries to use prefixed table names

## [2.3.16] - 2025-04-27

### Fixed
- **Circular Import**: Fixed circular import in `loader.py` when SwX loader tries to reload modules
- **Module Loading**: Added `_loading_modules` tracking to prevent recursive loading

## [2.0.0] - 2024-03-XX

### Added
- **Base Classes Pattern**: BaseController, BaseService, BaseRepository for rapid development
- **Domain Separation**: Admin, User, and System domains completely isolated
- **OAuth2 + JWT**: Secure token-based authentication with refresh tokens
- **Permission-First RBAC**: Fine-grained access control with team scoping
- **Policy Engine (ABAC)**: Attribute-based access control with conditions
- **Billing & Entitlements**: Feature registry, plan management, Stripe integration
- **Rate Limiting**: Plan-based rate limits with burst protection
- **Audit Logging**: Immutable security and business event logs
- **Background Jobs**: Asynchronous job processing with retries
- **CLI Tools**: `swx` command for scaffolding with `--base` flag
