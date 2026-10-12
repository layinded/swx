"""
PII Encryption Service — encrypt-on-write / decrypt-on-read for user PII.

Dual-write strategy:
    - On write: encrypt email and full_name into email_encrypted / full_name_encrypted
    - On read:  decrypt from *_encrypted columns, falling back to plaintext if encrypted
                column is NULL (supports gradual migration)

Uses the existing EncryptionService via encrypt_pii_field / decrypt_pii_field
which prefix ciphertext with ``pii:`` for auditor distinguishability.

This module contains NO database queries — those belong in user_repository.py
per SWX Controller → Service → Repository pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from swx_core.config.settings import settings
from swx_core.security.encryption import (
    decrypt_pii_field,
    encrypt_pii_field,
)

if TYPE_CHECKING:
    from swx_core.models.user import User


def encrypt_email(email: str) -> str:
    """Encrypt an email address for at-rest storage."""
    return encrypt_pii_field(email)


def decrypt_email(ciphertext: str) -> str:
    """Decrypt an email address, supporting both pii:-prefixed and plain ciphertext."""
    return decrypt_pii_field(ciphertext)


def encrypt_full_name(full_name: str) -> str:
    """Encrypt a full name for at-rest storage."""
    return encrypt_pii_field(full_name)


def decrypt_full_name(ciphertext: str) -> str:
    """Decrypt a full name, supporting both pii:-prefixed and plain ciphertext."""
    return decrypt_pii_field(ciphertext)


def pii_encryption_enabled() -> bool:
    """Check whether PII encryption is enabled via settings."""
    return settings.PII_ENCRYPTION_ENABLED


def should_encrypt_pii() -> bool:
    """Return True if PII encryption is enabled AND the encryption key is configured.

    This is the single gate-check that callers should use before attempting
    to read/write encrypted columns.
    """
    return pii_encryption_enabled() and bool(settings.SWX_ENCRYPTION_KEY)


def encrypt_user_pii(user: User) -> None:
    """Dual-write: encrypt PII fields on a User model into *_encrypted columns.

    Mutates user.email_encrypted and user.full_name_encrypted in-place.
    Does nothing when PII encryption is disabled.
    """
    if not should_encrypt_pii():
        return
    if user.email:
        user.email_encrypted = encrypt_email(user.email)
    if user.full_name:
        user.full_name_encrypted = encrypt_full_name(user.full_name)


def decrypt_user_pii(user: User) -> None:
    """Decrypt encrypted PII columns back into plaintext fields on a User model.

    When the encrypted column is populated, overwrites user.email /
    user.full_name with the decrypted value.  When it's NULL (pre-migration
    rows), the plaintext field is left untouched.
    """
    if not pii_encryption_enabled():
        return
    if user.email_encrypted:
        user.email = decrypt_email(user.email_encrypted)
    if user.full_name_encrypted:
        user.full_name = decrypt_full_name(user.full_name_encrypted)