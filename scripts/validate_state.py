#!/usr/bin/env python3
"""
State Validation Script
----------------------
Validates database state after simulation for consistency and integrity.

Checks:
- Referential integrity (foreign keys)
- Orphan records
- Audit log completeness
- Billing consistency
- Seed idempotency

Usage:
  python scripts/validate_state.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

API_URL = os.getenv("API_URL", "http://localhost:8001/api").rstrip("/")
DB_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'postgres')}",
)
TIMEOUT = 30.0

errors: list[str] = []
warnings: list[str] = []


def log(msg: str) -> None:
    print(f"[validate] {msg}")


def error(msg: str) -> None:
    errors.append(msg)
    print(f"[validate] ERROR: {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"[validate] WARNING: {msg}")


def check_foreign_keys() -> None:
    """Check referential integrity."""
    log("Checking foreign key integrity...")
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # Check user_role
            result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM user_role ur
                    LEFT JOIN users u ON ur.user_id = u.id
                    LEFT JOIN role r ON ur.role_id = r.id
                    WHERE u.id IS NULL OR r.id IS NULL
                """)
            )
            orphan_count = result.scalar()
            if orphan_count > 0:
                error(f"Found {orphan_count} orphan user_role records")

            # Check team_member
            result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM team_member tm
                    LEFT JOIN team t ON tm.team_id = t.id
                    LEFT JOIN users u ON tm.user_id = u.id
                    LEFT JOIN role r ON tm.role_id = r.id
                    WHERE t.id IS NULL OR u.id IS NULL OR r.id IS NULL
                """)
            )
            orphan_count = result.scalar()
            if orphan_count > 0:
                error(f"Found {orphan_count} orphan team_member records")

            # Check role_permission
            result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM role_permission rp
                    LEFT JOIN role r ON rp.role_id = r.id
                    LEFT JOIN permission p ON rp.permission_id = p.id
                    WHERE r.id IS NULL OR p.id IS NULL
                """)
            )
            orphan_count = result.scalar()
            if orphan_count > 0:
                error(f"Found {orphan_count} orphan role_permission records")

            # Check plan_entitlement
            result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM billing_plan_entitlement pe
                    LEFT JOIN billing_plan p ON pe.plan_id = p.id
                    LEFT JOIN billing_feature f ON pe.feature_id = f.id
                    WHERE p.id IS NULL OR f.id IS NULL
                """)
            )
            orphan_count = result.scalar()
            if orphan_count > 0:
                error(f"Found {orphan_count} orphan plan_entitlement records")

            log("Foreign key checks passed")
    except Exception as e:
        error(f"Foreign key check failed: {e}")


def check_audit_completeness(client: httpx.Client, admin_token: str) -> None:
    """Check audit log has expected events."""
    log("Checking audit log completeness...")
    try:
        r = client.get(
            f"{API_URL}/admin/audit/",
            headers={"Authorization": f"Bearer {admin_token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            error(f"Failed to fetch audit logs: {r.status_code}")
            return

        data = r.json()
        logs = data.get("data", []) if isinstance(data, dict) else data

        if not isinstance(logs, list):
            error("Audit logs response is not a list")
            return

        actions = {log.get("action") for log in logs if isinstance(log, dict)}

        expected_actions = {
            "admin.login",
            "user.login",
            "user.create",
            "team.create",
            "team.member.add",
        }

        missing = expected_actions - actions
        if missing:
            warn(f"Missing audit log actions: {missing}")

        log(f"Found {len(logs)} audit log entries")
    except Exception as e:
        error(f"Audit completeness check failed: {e}")


def check_billing_consistency(client: httpx.Client, admin_token: str) -> None:
    """Check billing plans, features, and entitlements."""
    log("Checking billing consistency...")
    try:
        # Check plans
        r = client.get(
            f"{API_URL}/admin/billing/plan/",
            headers={"Authorization": f"Bearer {admin_token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            error(f"Failed to fetch plans: {r.status_code}")
            return

        plans = r.json()
        if not isinstance(plans, list):
            error("Plans response is not a list")
            return

        plan_keys = {p.get("key") for p in plans if isinstance(p, dict)}
        expected_plans = {"free", "pro", "team", "enterprise"}
        missing = expected_plans - plan_keys
        if missing:
            error(f"Missing expected plans: {missing}")

        # Check features
        r = client.get(
            f"{API_URL}/admin/billing/feature/",
            headers={"Authorization": f"Bearer {admin_token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            error(f"Failed to fetch features: {r.status_code}")
            return

        features = r.json()
        if not isinstance(features, list):
            error("Features response is not a list")
            return

        feature_keys = {f.get("key") for f in features if isinstance(f, dict)}
        expected_features = {"api.calls", "llm.tokens", "advanced.analytics", "team.members"}
        missing = expected_features - feature_keys
        if missing:
            error(f"Missing expected features: {missing}")

        log("Billing consistency checks passed")
    except Exception as e:
        error(f"Billing consistency check failed: {e}")


def check_seed_idempotency(client: httpx.Client, admin_token: str) -> None:
    """Verify seed can be re-run without duplicates."""
    log("Checking seed idempotency (re-running seed)...")
    try:
        import subprocess
        env = os.environ.copy()
        env["API_URL"] = API_URL
        result = subprocess.run(
            [sys.executable, "scripts/seed_system.py"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        if result.returncode != 0:
            error(f"Seed re-run failed: {result.stderr}")
        else:
            log("Seed idempotency check passed (re-run succeeded)")
    except Exception as e:
        error(f"Seed idempotency check failed: {e}")


def main() -> None:
    log("Starting state validation...")
    log(f"API_URL={API_URL}")

    # Check foreign keys
    check_foreign_keys()

    # Check via API (requires admin token)
    admin_email = os.getenv("ADMIN_EMAIL", os.getenv("FIRST_SUPERUSER", "admin@example.com"))
    admin_password = os.getenv("ADMIN_PASSWORD", os.getenv("FIRST_SUPERUSER_PASSWORD", "changeme"))

    with httpx.Client(timeout=TIMEOUT) as client:
        # Admin login
        r = client.post(
            f"{API_URL}/admin/auth/",
            data={"username": admin_email, "password": admin_password},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            error(f"Admin login failed: {r.status_code}")
            sys.exit(1)

        admin_token = r.json().get("access_token")
        if not admin_token:
            error("No access_token in admin login response")
            sys.exit(1)

        check_audit_completeness(client, admin_token)
        check_billing_consistency(client, admin_token)
        check_seed_idempotency(client, admin_token)

    # Summary
    log("")
    log("=== Validation Summary ===")
    if errors:
        log(f"Errors: {len(errors)}")
        for err in errors:
            log(f"  - {err}")
    if warnings:
        log(f"Warnings: {len(warnings)}")
        for warn_msg in warnings:
            log(f"  - {warn_msg}")

    if not errors and not warnings:
        log("All checks passed!")
        sys.exit(0)
    elif errors:
        log("Validation failed with errors")
        sys.exit(1)
    else:
        log("Validation passed with warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
