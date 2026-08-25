# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Encryption Settings Mixin.

Defines at-rest field encryption configuration: master encryption keys,
previous key for rotation, PBKDF2 salt, and PII encryption toggle.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class EncryptionSettingsMixin(BaseSettings):
    """At-rest encryption configuration."""

    # Encryption Settings
    SWX_ENCRYPTION_KEY: str | None = Field(
        default=None,
        description="Master encryption key for at-rest field encryption. Required to enable encryption.",
    )
    SWX_ENCRYPTION_KEY_PREVIOUS: str | None = Field(
        default=None,
        description="Previous master key for key rotation. Enables dual-key decryption window.",
    )
    SWX_ENCRYPTION_SALT: str = Field(
        default="swx-default-encryption-salt",
        description="PBKDF2 salt for encryption key derivation. Changing this invalidates all existing encrypted data.",
    )
    PII_ENCRYPTION_ENABLED: bool = Field(
        default=False,
        description=(
            "When True, PII fields (email, full_name) are encrypted at rest using "
            "the EncryptionService. Requires SWX_ENCRYPTION_KEY to be set. "
            "During dual-write migration, plaintext columns are preserved alongside "
            "encrypted columns."
        ),
    )
