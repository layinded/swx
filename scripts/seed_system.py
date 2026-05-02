#!/usr/bin/env python3
"""
System Seed Script
------------------
Idempotent seeding via Admin API only. Seeds:
- Core permissions
- Core roles (admin, team_owner, team_member) and permission assignments
- Billing features, plans, and plan entitlements

Requires: API running, admin credentials (FIRST_SUPERUSER / FIRST_SUPERUSER_PASSWORD).
Usage: API_URL=/api python scripts/seed_system.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8001/api").rstrip("/")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", os.getenv("FIRST_SUPERUSER", "admin@example.com"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", os.getenv("FIRST_SUPERUSER_PASSWORD", "securepassword"))
TIMEOUT = 30.0


def log(msg: str) -> None:
    print(f"[seed] {msg}")


def fail(msg: str) -> None:
    print(f"[seed] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def admin_login(client: httpx.Client) -> str:
    r = client.post(
        f"{API_URL}/admin/auth/",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        fail(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("access_token")
    if not token:
        fail("Admin login: no access_token")
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

PERMISSIONS = [
    {"name": "user:read", "resource_type": "user", "action": "read", "description": "Read user profiles"},
    {"name": "user:write", "resource_type": "user", "action": "write", "description": "Create/update users"},
    {"name": "team:read", "resource_type": "team", "action": "read", "description": "Read teams"},
    {"name": "team:write", "resource_type": "team", "action": "write", "description": "Create/update teams"},
    {"name": "team:manage", "resource_type": "team", "action": "manage", "description": "Full team management"},
    {"name": "billing:read", "resource_type": "billing", "action": "read", "description": "Read billing/plans"},
    {"name": "billing:write", "resource_type": "billing", "action": "write", "description": "Manage subscriptions"},
    {"name": "audit:read", "resource_type": "audit", "action": "read", "description": "Read audit logs"},
    {"name": "job:read", "resource_type": "job", "action": "read", "description": "List/view jobs"},
    {"name": "job:write", "resource_type": "job", "action": "write", "description": "Retry jobs"},
    {"name": "policy:read", "resource_type": "policy", "action": "read", "description": "List/view policies"},
    {"name": "policy:write", "resource_type": "policy", "action": "write", "description": "Create/update policies"},
]


def seed_permissions(client: httpx.Client, token: str) -> dict[str, str]:
    """Create permissions if missing. Returns name -> id."""
    r = client.get(f"{API_URL}/admin/permission/", params={"limit": 1000}, headers=auth_headers(token), timeout=TIMEOUT)
    if r.status_code != 200:
        fail(f"List permissions failed: {r.status_code} {r.text}")
    existing = {p["name"]: p["id"] for p in r.json()}
    name_to_id = dict(existing)

    for p in PERMISSIONS:
        if p["name"] in existing:
            log(f"Permission {p['name']} already exists")
            continue
        r = client.post(f"{API_URL}/admin/permission/", json=p, headers=auth_headers(token), timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            fail(f"Create permission {p['name']} failed: {r.status_code} {r.text}")
        name_to_id[p["name"]] = r.json()["id"]
        log(f"Created permission {p['name']}")

    return name_to_id


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

ROLES = [
    {"name": "admin", "description": "Admin full access", "domain": "admin"},
    {"name": "team_owner", "description": "Team owner", "domain": "user"},
    {"name": "team_member", "description": "Team member", "domain": "user"},
]

# role name -> list of permission names
ROLE_PERMISSIONS = {
    "admin": [
        "user:read", "user:write", "team:read", "team:write", "team:manage",
        "billing:read", "billing:write", "audit:read", "job:read", "job:write",
        "policy:read", "policy:write",
    ],
    "team_owner": ["user:read", "team:read", "team:write", "team:manage", "billing:read", "billing:write"],
    "team_member": ["user:read", "team:read"],
}


def seed_roles(client: httpx.Client, token: str) -> dict[str, str]:
    """Create roles if missing. Returns name -> id."""
    r = client.get(f"{API_URL}/admin/role/", params={"limit": 1000}, headers=auth_headers(token), timeout=TIMEOUT)
    if r.status_code != 200:
        fail(f"List roles failed: {r.status_code} {r.text}")
    existing = {x["name"]: x["id"] for x in r.json()}
    name_to_id = dict(existing)

    for role in ROLES:
        if role["name"] in existing:
            log(f"Role {role['name']} already exists")
            continue
        r = client.post(f"{API_URL}/admin/role/", json=role, headers=auth_headers(token), timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            fail(f"Create role {role['name']} failed: {r.status_code} {r.text}")
        name_to_id[role["name"]] = r.json()["id"]
        log(f"Created role {role['name']}")

    return name_to_id


def assign_role_permissions(
    client: httpx.Client, token: str,
    role_ids: dict[str, str], perm_ids: dict[str, str],
) -> None:
    for role_name, perm_names in ROLE_PERMISSIONS.items():
        role_id = role_ids.get(role_name)
        if not role_id:
            continue
        r = client.get(
            f"{API_URL}/admin/role/{role_id}/permission",
            headers=auth_headers(token),
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            fail(f"List role permissions for {role_name} failed: {r.status_code} {r.text}")
        assigned = {x["permission_id"] for x in r.json()}
        for pname in perm_names:
            pid = perm_ids.get(pname)
            if not pid or pid in assigned:
                continue
            r = client.post(
                f"{API_URL}/admin/role/{role_id}/permission/{pid}",
                headers=auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code not in (200, 201):
                fail(f"Assign {pname} to {role_name} failed: {r.status_code} {r.text}")
            assigned.add(pid)
            log(f"Assigned {pname} -> {role_name}")


# ---------------------------------------------------------------------------
# Billing features
# ---------------------------------------------------------------------------

FEATURES = [
    {"key": "api.calls", "name": "API Calls", "description": "API request quota", "feature_type": "QUOTA", "unit": "requests"},
    {"key": "llm.tokens", "name": "LLM Tokens", "description": "LLM token quota", "feature_type": "QUOTA", "unit": "tokens"},
    {"key": "advanced.analytics", "name": "Advanced Analytics", "description": "Analytics feature", "feature_type": "BOOLEAN", "unit": None},
    {"key": "team.members", "name": "Team Members", "description": "Team member quota", "feature_type": "QUOTA", "unit": "members"},
]


def seed_features(client: httpx.Client, token: str) -> dict[str, str]:
    r = client.get(f"{API_URL}/admin/billing/feature/", headers=auth_headers(token), timeout=TIMEOUT)
    if r.status_code != 200:
        fail(f"List features failed: {r.status_code} {r.text}")
    existing = {f["key"]: f["id"] for f in r.json()}
    key_to_id = dict(existing)

    for f in FEATURES:
        if f["key"] in existing:
            log(f"Feature {f['key']} already exists")
            continue
        r = client.post(f"{API_URL}/admin/billing/feature/", json=f, headers=auth_headers(token), timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            fail(f"Create feature {f['key']} failed: {r.status_code} {r.text}")
        key_to_id[f["key"]] = r.json()["id"]
        log(f"Created feature {f['key']}")

    return key_to_id


# ---------------------------------------------------------------------------
# Plans and entitlements
# ---------------------------------------------------------------------------

PLANS = [
    {"key": "free", "name": "Free Plan", "description": "Free tier", "is_active": True, "is_public": True},
    {"key": "pro", "name": "Pro Plan", "description": "Pro tier", "is_active": True, "is_public": True},
    {"key": "team", "name": "Team Plan", "description": "Team collaboration", "is_active": True, "is_public": True},
    {"key": "enterprise", "name": "Enterprise Plan", "description": "Enterprise tier", "is_active": True, "is_public": True},
]

ENTITLEMENTS: dict[str, dict[str, str]] = {
    "free": {"api.calls": "100", "llm.tokens": "1000", "advanced.analytics": "false"},
    "pro": {"api.calls": "10000", "llm.tokens": "100000", "advanced.analytics": "true"},
    "team": {"api.calls": "50000", "llm.tokens": "500000", "advanced.analytics": "true", "team.members": "50"},
    "enterprise": {"api.calls": "500000", "llm.tokens": "5000000", "advanced.analytics": "true", "team.members": "500"},
}


def seed_plans(client: httpx.Client, token: str) -> dict[str, str]:
    r = client.get(f"{API_URL}/admin/billing/plan/", headers=auth_headers(token), timeout=TIMEOUT)
    if r.status_code != 200:
        fail(f"List plans failed: {r.status_code} {r.text}")
    existing = {p["key"]: p["id"] for p in r.json()}
    key_to_id = dict(existing)

    for p in PLANS:
        if p["key"] in existing:
            log(f"Plan {p['key']} already exists")
            continue
        r = client.post(f"{API_URL}/admin/billing/plan/", json=p, headers=auth_headers(token), timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            fail(f"Create plan {p['key']} failed: {r.status_code} {r.text}")
        key_to_id[p["key"]] = r.json()["id"]
        log(f"Created plan {p['key']}")

    return key_to_id


def seed_entitlements(
    client: httpx.Client, token: str,
    plan_ids: dict[str, str], feature_ids: dict[str, str],
) -> None:
    for plan_key, feats in ENTITLEMENTS.items():
        plan_id = plan_ids.get(plan_key)
        if not plan_id:
            continue
        for fkey, value in feats.items():
            fid = feature_ids.get(fkey)
            if not fid:
                continue
            r = client.post(
                f"{API_URL}/admin/billing/plan/{plan_id}/entitlement/{fid}",
                params={"value": value},
                headers=auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code in (200, 201):
                log(f"Entitlement {plan_key} + {fkey}={value}")
            elif "duplicate" in r.text.lower() or "unique" in r.text.lower() or "already" in r.text.lower():
                log(f"Entitlement {plan_key} + {fkey} already exists")
            else:
                fail(f"Entitlement {plan_key} + {fkey} failed: {r.status_code} {r.text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log("Starting system seed (idempotent)")
    log(f"API_URL={API_URL} ADMIN_EMAIL={ADMIN_EMAIL}")

    with httpx.Client(timeout=TIMEOUT) as client:
        token = admin_login(client)
        log("Admin logged in")

        perm_ids = seed_permissions(client, token)
        role_ids = seed_roles(client, token)
        assign_role_permissions(client, token, role_ids, perm_ids)

        feature_ids = seed_features(client, token)
        plan_ids = seed_plans(client, token)
        seed_entitlements(client, token, plan_ids, feature_ids)
        
        # Seed runtime settings
        log("Seeding runtime settings...")
        seed_settings(client, token)

    log("System seed complete")


def seed_settings(client: httpx.Client, token: str) -> None:
    """Seed default runtime settings if missing."""
    # Import here to avoid circular dependency
    import sys
    from pathlib import Path
    seed_settings_path = Path(__file__).parent / "seed_settings.py"
    if seed_settings_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("seed_settings", seed_settings_path)
        seed_settings_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_settings_module)
        DEFAULT_SETTINGS = seed_settings_module.DEFAULT_SETTINGS
    else:
        log("Warning: seed_settings.py not found, skipping settings seed")
        return
    
    # Get existing settings
    r = client.get(
        f"{API_URL}/admin/settings/",
        params={"limit": 1000},
        headers=auth_headers(token),
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        log(f"Warning: List settings failed: {r.status_code} (settings API may not be available yet)")
        return
    
    existing = {s["key"]: s for s in r.json()}
    
    # Create missing settings
    for setting in DEFAULT_SETTINGS:
        key = setting["key"]
        if key in existing:
            log(f"Setting {key} already exists")
            continue
        
        # Skip if value is empty
        if not setting.get("value"):
            log(f"Skipping {key} (empty value)")
            continue
        
        r = client.post(
            f"{API_URL}/admin/settings/",
            json=setting,
            headers=auth_headers(token),
            timeout=TIMEOUT,
        )
        if r.status_code in (200, 201):
            log(f"Created setting {key}")
        else:
            log(f"Warning: Create setting {key} failed: {r.status_code} {r.text}")


if __name__ == "__main__":
    main()
