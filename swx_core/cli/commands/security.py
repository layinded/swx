"""Security CLI Commands
----------------------
Admin commands for encryption and security operations.

``swx security:encrypt-secrets`` — Find and encrypt plaintext secrets
(webhook secrets, SSO client secrets, refresh tokens, LLM API keys) that
are stored in cleartext.  Uses the versioned Fernet service from
``swx_core.security.encryption`` so all ciphertext is prefixed with ``v1:``
or ``v2:`` for safe key rotation.

The command is **idempotent** — it skips rows whose values already match
the Fernet token pattern (``gAAAA…``) or have a version prefix (``v1:…``).
"""

from __future__ import annotations

import asyncio
import re

import click

_FERNET_TOKEN_PATTERN = re.compile(r"^gAAAA[A-Za-z0-9_-]+=*$")
_VERSION_PREFIX_PATTERN = re.compile(r"^v[1-9]\d*:")


def _is_encrypted(value: str | None) -> bool:
    """Return True if *value* looks like an already-encrypted string."""
    if value is None:
        return True  # NULL columns are fine
    if not value:
        return True  # empty strings are fine
    return bool(_FERNET_TOKEN_PATTERN.match(value)) or bool(_VERSION_PREFIX_PATTERN.match(value))


async def _encrypt_secrets(dry_run: bool = False) -> dict[str, int]:
    """Scan and encrypt plaintext secrets across all affected tables.

    Returns a dict with counts per table: {table: encrypted_count}.
    """
    from swx_core.database.db import async_session
    from swx_core.security.encryption import encrypt_value
    from sqlalchemy import select, update, text

    results: dict[str, int] = {}

    # --- 1. Webhook secrets (swx_webhook_endpoint.secret) ---
    from swx_core.models.webhook_endpoint import WebhookEndpoint
    async with async_session() as session:
        stmt = select(WebhookEndpoint.id, WebhookEndpoint.secret).where(WebhookEndpoint.secret.isnot(None))  # pyright: ignore[reportCallIssue,reportArgumentType,reportAttributeAccessIssue,reportOptionalMemberAccess]
        rows = (await session.execute(stmt)).all()
        count = 0
        for row_id, secret in rows:
            if _is_encrypted(secret):
                continue
            if not dry_run:
                await session.execute(update(WebhookEndpoint).where(WebhookEndpoint.id == row_id).values(secret=encrypt_value(secret)))
            count += 1
        if not dry_run and count > 0:
            await session.commit()
        results["swx_webhook_endpoint"] = count

    # --- 2. SSO provider client_secret + certificate (swx_sso_provider) ---
    from swx_core.models.sso_provider import SSOProvider
    async with async_session() as session:
        stmt = select(SSOProvider.id, SSOProvider.client_secret, SSOProvider.certificate).where(  # pyright: ignore[reportCallIssue,reportArgumentType]
            SSOProvider.client_secret.isnot(None) | SSOProvider.certificate.isnot(None)  # pyright: ignore[reportAttributeAccessIssue,reportOptionalMemberAccess]
        )
        rows = (await session.execute(stmt)).all()
        count = 0
        for row_id, client_secret, certificate in rows:
            updates = {}
            if client_secret and not _is_encrypted(client_secret):
                updates["client_secret"] = encrypt_value(client_secret)
            if certificate and not _is_encrypted(certificate):
                updates["certificate"] = encrypt_value(certificate)
            if updates and not dry_run:
                await session.execute(update(SSOProvider).where(SSOProvider.id == row_id).values(**updates))
            if updates:
                count += 1
        if not dry_run and count > 0:
            await session.commit()
        results["swx_sso_provider"] = count

    # --- 3. Refresh tokens (swx_refresh_token.token) ---
    from swx_core.models.refresh_token import RefreshToken
    async with async_session() as session:
        stmt = select(RefreshToken.id, RefreshToken.token).where(RefreshToken.token.isnot(None))  # pyright: ignore[reportCallIssue,reportArgumentType,reportAttributeAccessIssue]
        rows = (await session.execute(stmt)).all()
        count = 0
        for row_id, token_value in rows:
            if _is_encrypted(token_value):
                continue
            if not dry_run:
                await session.execute(update(RefreshToken).where(RefreshToken.id == row_id).values(token=encrypt_value(token_value)))
            count += 1
        if not dry_run and count > 0:
            await session.commit()
        results["swx_refresh_token"] = count

    # --- 4. LLM provider encrypted_api_key (swx_llm_provider_config) ---
    from swx_core.models.llm_provider_config import LLMProviderConfig
    async with async_session() as session:
        stmt = select(LLMProviderConfig.id, LLMProviderConfig.encrypted_api_key).where(LLMProviderConfig.encrypted_api_key.isnot(None))  # pyright: ignore[reportCallIssue,reportArgumentType,reportAttributeAccessIssue,reportOptionalMemberAccess]
        rows = (await session.execute(stmt)).all()
        count = 0
        for row_id, api_key in rows:
            if _is_encrypted(api_key):
                continue
            if not dry_run:
                await session.execute(update(LLMProviderConfig).where(LLMProviderConfig.id == row_id).values(encrypted_api_key=encrypt_value(api_key)))
            count += 1
        if not dry_run and count > 0:
            await session.commit()
        results["swx_llm_provider_config"] = count

    return results


@click.group()
def security():
    """Security management commands."""
    pass


@security.command("encrypt-secrets")
@click.option("--dry-run", is_flag=True, help="Show what would be encrypted without making changes.")
def encrypt_secrets(dry_run: bool):
    """Encrypt plaintext secrets in the database.

    Scans webhook secrets, SSO client secrets/certificates, refresh tokens,
    and LLM API keys.  Rows already containing encrypted values (Fernet
    tokens or versioned ciphertext) are skipped.

    Requires SWX_ENCRYPTION_KEY to be configured.
    """
    from swx_core.config.settings import settings

    if not settings.SWX_ENCRYPTION_KEY:
        click.secho("Error: SWX_ENCRYPTION_KEY is not set. Configure it before running this command.", fg="red")
        raise SystemExit(1)

    if dry_run:
        click.secho("Running in DRY RUN mode — no changes will be made.", fg="yellow")

    try:
        results = asyncio.run(_encrypt_secrets(dry_run=dry_run))
    except Exception as exc:
        click.secho(f"Error during encryption: {exc}", fg="red")
        raise SystemExit(1)

    total = sum(results.values())
    if total == 0:
        click.secho("No plaintext secrets found — all values are already encrypted.", fg="green")
        return

    verb = "Would encrypt" if dry_run else "Encrypted"
    for table, count in results.items():
        if count > 0:
            click.echo(f"  {verb} {count} row(s) in {table}")

    click.secho(f"{verb} {total} secret(s) total.", fg="green")