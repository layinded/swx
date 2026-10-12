# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.security.encryption — versioned Fernet encryption with key rotation."""

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from swx_core.security.encryption import (
    EncryptionService,
    KeyVersion,
    _VERSION_PREFIX_PATTERN,
    _derive_fernet_key,
    decrypt_api_key,
    decrypt_value,
    encrypt_api_key,
    encrypt_value,
    is_encrypted,
)
from swx_core.utils.errors import DecryptionError, EncryptionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_master_key() -> str:
    """Generate a random 32-byte master key for testing."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _make_settings(**overrides: object) -> MagicMock:
    """Build a mock settings object with encryption-related attributes."""
    defaults: dict[str, object] = {
        "SWX_ENCRYPTION_KEY": _make_master_key(),
        "SWX_ENCRYPTION_KEY_PREVIOUS": None,
        "SWX_ENCRYPTION_SALT": "test-salt",
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ---------------------------------------------------------------------------
# _derive_fernet_key
# ---------------------------------------------------------------------------

class TestDeriveFernetKey:
    """Unit tests for the PBKDF2 key derivation helper."""

    def test_derives_consistent_key(self) -> None:
        """Same inputs produce the same derived key."""
        master = _make_master_key()
        salt = b"my-salt"
        k1 = _derive_fernet_key(master, salt)
        k2 = _derive_fernet_key(master, salt)
        assert k1 == k2

    def test_different_master_produces_different_key(self) -> None:
        """Different master keys produce different derived keys."""
        k1 = _derive_fernet_key(_make_master_key(), b"salt")
        k2 = _derive_fernet_key(_make_master_key(), b"salt")
        assert k1 != k2

    def test_different_salt_produces_different_key(self) -> None:
        """Different salts produce different derived keys."""
        master = _make_master_key()
        k1 = _derive_fernet_key(master, b"salt-a")
        k2 = _derive_fernet_key(master, b"salt-b")
        assert k1 != k2


# ---------------------------------------------------------------------------
# KeyVersion
# ---------------------------------------------------------------------------

class TestKeyVersion:
    """Unit tests for the KeyVersion dataclass."""

    def test_label_format(self) -> None:
        """KeyVersion.label returns 'v{version}'."""
        fernet = Fernet(Fernet.generate_key())
        kv = KeyVersion(version=3, primary_fernet=fernet)
        assert kv.label == "v3"

    def test_encrypt_decrypt_round_trip(self) -> None:
        """Encrypt then decrypt returns the original plaintext."""
        fernet = Fernet(Fernet.generate_key())
        kv = KeyVersion(version=1, primary_fernet=fernet)
        plaintext = "secret-value-123"
        ciphertext = kv.encrypt(plaintext)
        assert ciphertext != plaintext
        assert kv.decrypt(ciphertext) == plaintext

    def test_decrypt_with_legacy_fallback(self) -> None:
        """When primary fails, legacy fallback is tried."""
        primary = Fernet(Fernet.generate_key())
        legacy = Fernet(Fernet.generate_key())
        kv = KeyVersion(version=1, primary_fernet=primary, legacy_fallback_fernet=legacy)
        # Encrypt with legacy, decrypt should succeed via fallback
        ciphertext = legacy.encrypt(b"hello").decode()
        assert kv.decrypt(ciphertext) == "hello"

    def test_decrypt_raises_when_both_fail(self) -> None:
        """DecryptionError raised when neither key can decrypt."""
        primary = Fernet(Fernet.generate_key())
        kv = KeyVersion(version=1, primary_fernet=primary)
        with pytest.raises(DecryptionError, match="Unable to decrypt"):
            kv.decrypt("not-valid-fernet-token")


# ---------------------------------------------------------------------------
# EncryptionService
# ---------------------------------------------------------------------------

class TestEncryptionService:
    """Tests for the EncryptionService class."""

    def test_encrypt_decrypt_round_trip(self) -> None:
        """Encrypt then decrypt returns the original plaintext."""
        svc = EncryptionService(_make_settings())
        plaintext = "my-secret-data"
        ciphertext = svc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert svc.decrypt(ciphertext) == plaintext

    def test_encrypt_empty_raises(self) -> None:
        """Encrypting an empty string raises EncryptionError."""
        svc = EncryptionService(_make_settings())
        with pytest.raises(EncryptionError, match="cannot be empty"):
            svc.encrypt("")

    def test_decrypt_empty_raises(self) -> None:
        """Decrypting an empty string raises DecryptionError."""
        svc = EncryptionService(_make_settings())
        with pytest.raises(DecryptionError, match="cannot be empty"):
            svc.decrypt("")

    def test_encrypt_prepends_version_label(self) -> None:
        """Ciphertext starts with 'v{version}:' prefix."""
        svc = EncryptionService(_make_settings())
        ciphertext = svc.encrypt("data")
        assert _VERSION_PREFIX_PATTERN.match(ciphertext) is not None
        assert ciphertext.startswith("v1:")

    def test_decrypt_invalid_ciphertext_raises(self) -> None:
        """Decrypting garbage raises DecryptionError."""
        svc = EncryptionService(_make_settings())
        with pytest.raises(DecryptionError):
            svc.decrypt("not-a-valid-fernet-token")

    def test_decrypt_unsupported_version_raises(self) -> None:
        """Decrypting with an unknown version prefix raises DecryptionError."""
        svc = EncryptionService(_make_settings())
        with pytest.raises(DecryptionError, match="Unsupported encryption key version"):
            svc.decrypt("v99:some-payload")

    def test_missing_encryption_key_raises(self) -> None:
        """EncryptionError raised when SWX_ENCRYPTION_KEY is not set."""
        svc = EncryptionService(_make_settings(SWX_ENCRYPTION_KEY=None))
        with pytest.raises(EncryptionError, match="SWX_ENCRYPTION_KEY is not configured"):
            svc.encrypt("data")

    def test_key_rotation_encrypt_current_decrypt_previous(self) -> None:
        """Encrypt with current key, decrypt with previous key during rotation."""
        previous_key = _make_master_key()
        current_key = _make_master_key()
        svc = EncryptionService(
            _make_settings(
                SWX_ENCRYPTION_KEY=current_key,
                SWX_ENCRYPTION_KEY_PREVIOUS=previous_key,
            )
        )
        plaintext = "rotate-me"
        ciphertext = svc.encrypt(plaintext)
        # Should be encrypted with v2 (current)
        assert ciphertext.startswith("v2:")
        # Decrypt should work
        assert svc.decrypt(ciphertext) == plaintext

    def test_key_rotation_decrypt_old_ciphertext(self) -> None:
        """Ciphertext encrypted with previous key can still be decrypted."""
        previous_key = _make_master_key()
        current_key = _make_master_key()
        # First, encrypt with only the "previous" key (simulating old state)
        svc_old = EncryptionService(
            _make_settings(SWX_ENCRYPTION_KEY=previous_key, SWX_ENCRYPTION_KEY_PREVIOUS=None)
        )
        plaintext = "old-data"
        old_ciphertext = svc_old.encrypt(plaintext)
        assert old_ciphertext.startswith("v1:")

        # Now rotate: current key is new, previous is old
        svc_new = EncryptionService(
            _make_settings(
                SWX_ENCRYPTION_KEY=current_key,
                SWX_ENCRYPTION_KEY_PREVIOUS=previous_key,
            )
        )
        # Should still be able to decrypt old ciphertext
        assert svc_new.decrypt(old_ciphertext) == plaintext

    def test_legacy_ciphertext_no_prefix(self) -> None:
        """Ciphertext without version prefix is decrypted with the oldest key."""
        svc = EncryptionService(_make_settings())
        plaintext = "legacy-data"
        # Encrypt normally to get a valid Fernet token, then strip the prefix
        full = svc.encrypt(plaintext)
        # full is "v1:<fernet-token>"
        payload = full.split(":", 1)[1]
        # Decrypt the raw payload (no prefix) — should use legacy path
        assert svc.decrypt(payload) == plaintext

    def test_cache_invalidation_on_config_change(self) -> None:
        """Changing the key config invalidates the cached versions."""
        key_a = _make_master_key()
        key_b = _make_master_key()
        settings_mock = _make_settings(
            SWX_ENCRYPTION_KEY=key_a,
            SWX_ENCRYPTION_KEY_PREVIOUS=None,
        )
        svc = EncryptionService(settings_mock)

        c1 = svc.encrypt("first")
        # Rotate: key_b becomes current, key_a becomes previous
        settings_mock.SWX_ENCRYPTION_KEY = key_b
        settings_mock.SWX_ENCRYPTION_KEY_PREVIOUS = key_a
        c2 = svc.encrypt("second")

        # Both should decrypt — c1 via previous key, c2 via current key
        assert svc.decrypt(c1) == "first"
        assert svc.decrypt(c2) == "second"


# ---------------------------------------------------------------------------
# is_encrypted
# ---------------------------------------------------------------------------

class TestIsEncrypted:
    """Tests for the is_encrypted() detection function."""

    def test_versioned_ciphertext_is_encrypted(self) -> None:
        """A string starting with 'v1:' is detected as encrypted."""
        assert is_encrypted("v1:gAAAAAB...") is True

    def test_plaintext_is_not_encrypted(self) -> None:
        """Plaintext strings are not detected as encrypted."""
        assert is_encrypted("hello world") is False
        assert is_encrypted("sk-abc123") is False

    def test_empty_string_is_not_encrypted(self) -> None:
        """Empty string is not detected as encrypted."""
        assert is_encrypted("") is False

    def test_v_prefix_without_colon_is_not_encrypted(self) -> None:
        """'v1' without colon is not detected as encrypted."""
        assert is_encrypted("v1something") is False


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for encrypt_value / decrypt_value / encrypt_api_key / decrypt_api_key."""

    def test_encrypt_value_decrypt_value_round_trip(self) -> None:
        """encrypt_value and decrypt_value work as a pair."""
        with patch.dict(os.environ, {"SWX_ENCRYPTION_KEY": _make_master_key()}):
            # Reset the module-level singleton
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            plaintext = "round-trip-test"
            ciphertext = encrypt_value(plaintext)
            assert ciphertext != plaintext
            assert decrypt_value(ciphertext) == plaintext

    def test_encrypt_api_key_decrypt_api_key_round_trip(self) -> None:
        """encrypt_api_key and decrypt_api_key are aliases that work."""
        with patch.dict(os.environ, {"SWX_ENCRYPTION_KEY": _make_master_key()}):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            api_key = "sk-abc123def456"
            ciphertext = encrypt_api_key(api_key)
            assert ciphertext != api_key
            assert decrypt_api_key(ciphertext) == api_key

    def test_encrypt_value_raises_without_key(self) -> None:
        """encrypt_value raises EncryptionError when no key is configured."""
        with patch.dict(os.environ, {}, clear=True):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None
            with pytest.raises(EncryptionError, match="SWX_ENCRYPTION_KEY is not configured"):
                encrypt_value("data")
