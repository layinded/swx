#!/usr/bin/env python3
"""
Settings Seed Script
--------------------
Idempotent seeding of default runtime settings into database.

Seeds:
- Token expiration settings (from .env defaults)
- Rate limit configurations
- Feature flags
- Email configuration (non-secret parts)
- Audit log retention
- Job processing configs

Requires: API running, admin credentials.
Usage: API_URL=/api python scripts/seed_settings.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8001/api").rstrip("/")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", os.getenv("FIRST_SUPERUSER", "admin@example.com"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", os.getenv("FIRST_SUPERUSER_PASSWORD", "securepassword"))
TIMEOUT = 30.0


def log(msg: str) -> None:
    print(f"[seed-settings] {msg}")


def fail(msg: str) -> None:
    print(f"[seed-settings] ERROR: {msg}", file=sys.stderr)
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


# Default settings to seed
DEFAULT_SETTINGS = [
    # Token Expiration (Security)
    {
        "key": "auth.access_token_expire_minutes",
        "value": str(60 * 24 * 7),  # 7 days
        "value_type": "int",
        "category": "security",
        "description": "Access token expiration in minutes",
    },
    {
        "key": "auth.refresh_token_expire_days",
        "value": "30",
        "value_type": "int",
        "category": "security",
        "description": "Refresh token expiration in days",
    },
    {
        "key": "auth.email_reset_token_expire_hours",
        "value": "48",
        "value_type": "int",
        "category": "security",
        "description": "Password reset token expiration in hours",
    },
    # Feature Flags
    {
        "key": "feature.enable_social_login",
        "value": "true",
        "value_type": "bool",
        "category": "feature_flag",
        "description": "Enable social login globally",
    },
    {
        "key": "feature.enable_google_login",
        "value": "true",
        "value_type": "bool",
        "category": "feature_flag",
        "description": "Enable Google OAuth login",
    },
    {
        "key": "feature.enable_facebook_login",
        "value": "false",
        "value_type": "bool",
        "category": "feature_flag",
        "description": "Enable Facebook OAuth login",
    },
    {
        "key": "feature.enable_github_login",
        "value": "false",
        "value_type": "bool",
        "category": "feature_flag",
        "description": "Enable GitHub OAuth login",
    },
    # Email Configuration (Non-secret)
    {
        "key": "email.from_email",
        "value": os.getenv("EMAILS_FROM_EMAIL", ""),
        "value_type": "string",
        "category": "email",
        "description": "Default 'from' email address",
    },
    {
        "key": "email.from_name",
        "value": os.getenv("EMAILS_FROM_NAME", "SwX API"),
        "value_type": "string",
        "category": "email",
        "description": "Default 'from' name",
    },
    # Audit Log
    {
        "key": "audit.retention_days",
        "value": "365",
        "value_type": "int",
        "category": "audit",
        "description": "Audit log retention in days",
    },
    # Job Processing
    {
        "key": "job.default_max_attempts",
        "value": "5",
        "value_type": "int",
        "category": "jobs",
        "description": "Default maximum retry attempts for jobs",
    },
    {
        "key": "job.default_retry_delay_seconds",
        "value": "60",
        "value_type": "int",
        "category": "jobs",
        "description": "Default retry delay in seconds",
    },
    {
        "key": "job.default_timeout_seconds",
        "value": "300",
        "value_type": "int",
        "category": "jobs",
        "description": "Default job timeout in seconds",
    },
]


def seed_settings(client: httpx.Client, token: str) -> None:
    """Seed default settings if missing."""
    # Get existing settings
    r = client.get(
        f"{API_URL}/admin/settings/",
        params={"limit": 1000},
        headers=auth_headers(token),
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        fail(f"List settings failed: {r.status_code} {r.text}")
    
    existing = {s["key"]: s for s in r.json()}
    
    # Create missing settings
    for setting in DEFAULT_SETTINGS:
        key = setting["key"]
        if key in existing:
            log(f"Setting {key} already exists")
            continue
        
        # Skip if value is empty (e.g., email.from_email not set)
        if not setting["value"]:
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
            fail(f"Create setting {key} failed: {r.status_code} {r.text}")


def main() -> None:
    log("Starting settings seed (idempotent)")
    log(f"API_URL={API_URL} ADMIN_EMAIL={ADMIN_EMAIL}")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        token = admin_login(client)
        log("Admin logged in")
        
        seed_settings(client, token)
    
    log("Settings seed complete")


if __name__ == "__main__":
    main()
