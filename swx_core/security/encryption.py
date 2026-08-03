"""Versioned Fernet encryption service with key rotation.

Provides at-rest encryption for sensitive fields (webhook secrets, SSO client
secrets, refresh tokens, LLM API keys) with a dual-key rotation window that
allows decrypting old ciphertext during key rollover.

Configuration (via swx_core.config.settings):
    SWX_ENCRYPTION_KEY: Current master key (required for encryption/decryption).
    SWX_ENCRYPTION_KEY_PREVIOUS: Previous master key (enables dual-key rotation).
    SWX_ENCRYPTION_SALT: PBKDF2 salt (defaults to "swx-default-encryption-salt").

Key derivation uses PBKDF2-HMAC-SHA256 with 480,000 iterations (OWASP 2023
recommendation for SHA-256). Ciphertext is prefixed with a version label
(e.g. "v1:...") so the correct key can be selected on decrypt.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from threading import RLock

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from swx_core.utils.errors import EncryptionError, DecryptionError

_DEFAULT_SALT = b"swx-default-encryption-salt"
_VERSION_PREFIX_PATTERN = re.compile(r"^v(?P<version>[1-9]\d*):(?P<payload>.+)$")


def _derive_fernet_key(master_key: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from a master key using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode()))


@dataclass(frozen=True, slots=True)
class KeyVersion:
    """A versioned Fernet key with an optional legacy fallback for rotation."""

    version: int
    primary_fernet: Fernet
    legacy_fallback_fernet: Fernet | None = None

    @property
    def label(self) -> str:
        return f"v{self.version}"

    def encrypt(self, plaintext: str) -> str:
        return self.primary_fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        tokens = [self.primary_fernet]
        if self.legacy_fallback_fernet is not None:
            tokens.append(self.legacy_fallback_fernet)

        for token in tokens:
            try:
                return token.decrypt(ciphertext.encode()).decode()
            except InvalidToken:
                continue

        raise DecryptionError(f"Unable to decrypt ciphertext with key version {self.label}.")


class EncryptionService:
    """Version-aware Fernet encryption with rotation-safe key resolution.

    Thread-safe via RLock on key resolution. Caches derived keys until
    configuration changes.
    """

    def __init__(self, settings_obj: object | None = None) -> None:
        self._settings: object = settings_obj
        self._lock: RLock = RLock()
        self._cached_signature: tuple[str, str | None, bytes] | None = None
        self._cached_versions: dict[int, KeyVersion] | None = None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext, returning a versioned ciphertext string."""
        if not plaintext:
            raise EncryptionError("Plaintext cannot be empty.")
        versions = self._resolve_versions()
        current_version = max(versions)
        key_version = versions[current_version]
        return f"{key_version.label}:{key_version.encrypt(plaintext)}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a versioned or legacy ciphertext string."""
        if not ciphertext:
            raise DecryptionError("Ciphertext cannot be empty.")

        versions = self._resolve_versions()
        match = _VERSION_PREFIX_PATTERN.match(ciphertext)

        if match is not None:
            version = int(match.group("version"))
            payload = match.group("payload")
            key_version = versions.get(version)
            if key_version is None:
                raise DecryptionError(f"Unsupported encryption key version: v{version}.")
            return key_version.decrypt(payload)

        # Legacy: no version prefix — try the lowest-version key (oldest)
        legacy_version = min(versions)
        return versions[legacy_version].decrypt(ciphertext)

    def _resolve_versions(self) -> dict[int, KeyVersion]:
        """Resolve and cache key versions from current settings."""
        if self._settings is None:
            from swx_core.config.settings import settings
            self._settings = settings

        signature = self._config_signature()

        with self._lock:
            if self._cached_signature == signature and self._cached_versions is not None:
                return self._cached_versions

            current_master_key = signature[0]
            previous_master_key = signature[1]
            primary_salt = signature[2]

            versions: dict[int, KeyVersion]
            if previous_master_key and previous_master_key != current_master_key:
                versions = {
                    1: self._build_key_version(1, previous_master_key, primary_salt, allow_legacy_fallback=True),
                    2: self._build_key_version(2, current_master_key, primary_salt, allow_legacy_fallback=False),
                }
            else:
                versions = {
                    1: self._build_key_version(1, current_master_key, primary_salt, allow_legacy_fallback=True),
                }

            self._cached_signature = signature
            self._cached_versions = versions
            return versions

    def _config_signature(self) -> tuple[str, str | None, bytes]:
        """Compute a cache-busting signature from the current key configuration."""
        current_master_key = self._get_setting("SWX_ENCRYPTION_KEY")
        if not current_master_key:
            raise EncryptionError(
                "SWX_ENCRYPTION_KEY is not configured. "
                "Set it in your environment or settings to enable encryption."
            )

        previous_master_key = self._get_setting("SWX_ENCRYPTION_KEY_PREVIOUS")
        primary_salt = self._salt_bytes()
        return current_master_key, previous_master_key, primary_salt

    def _build_key_version(
        self,
        version: int,
        master_key: str,
        primary_salt: bytes,
        *,
        allow_legacy_fallback: bool,
    ) -> KeyVersion:
        """Build a KeyVersion with an optional legacy fallback for rotation."""
        primary_fernet = Fernet(_derive_fernet_key(master_key, primary_salt))
        legacy_fallback_fernet: Fernet | None = None

        if allow_legacy_fallback and primary_salt != _DEFAULT_SALT:
            legacy_fallback_fernet = Fernet(_derive_fernet_key(master_key, _DEFAULT_SALT))

        return KeyVersion(
            version=version,
            primary_fernet=primary_fernet,
            legacy_fallback_fernet=legacy_fallback_fernet,
        )

    def _salt_bytes(self) -> bytes:
        """Resolve the encryption salt from settings."""
        salt = self._get_setting("SWX_ENCRYPTION_SALT")
        if not salt:
            return _DEFAULT_SALT
        return salt.encode()

    def _get_setting(self, name: str) -> str | None:
        """Read a setting from the settings object, falling back to env var."""
        value = getattr(self._settings, name, None) if self._settings else None
        if value is None or value == "":
            import os
            value = os.getenv(name)
        if value is None:
            return None
        return str(value)


def is_encrypted(value: str) -> bool:
    """Check whether a string looks like a versioned Fernet ciphertext."""
    return bool(_VERSION_PREFIX_PATTERN.match(value))


# Module-level singleton — lazy-initialised on first use.
_encryption_service: EncryptionService | None = None


def _get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_value(plaintext: str) -> str:
    """Encrypt a value using the configured encryption key."""
    return _get_encryption_service().encrypt(plaintext)


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a value using the configured encryption key."""
    return _get_encryption_service().decrypt(ciphertext)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key. Alias for encrypt_value with domain-specific naming."""
    return encrypt_value(plaintext)


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key. Alias for decrypt_value with domain-specific naming."""
    return decrypt_value(ciphertext)