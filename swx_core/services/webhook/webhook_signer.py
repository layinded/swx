import hashlib
import hmac
import json
from typing import Any

from swx_core.security.encryption import decrypt_value, is_encrypted
from swx_core.services.llm.config_resolver import resolve_config


def _resolve_secret(secret: str) -> str:
    """Resolve a webhook secret: first expand ${ENV_VAR} patterns, then decrypt if Fernet-encrypted."""
    resolved = resolve_config({"secret": secret}).get("secret") or ""
    resolved = str(resolved)
    if is_encrypted(resolved):
        try:
            resolved = decrypt_value(resolved)
        except Exception:
            pass
    return resolved


def _payload_bytes(payload: dict[str, Any] | str | bytes) -> bytes:
    if isinstance(payload, bytes):
        return payload
    elif isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_payload(secret: str, payload: dict[str, Any] | str | bytes) -> str:
    return hmac.new(_resolve_secret(secret).encode("utf-8"), _payload_bytes(payload), hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: dict[str, Any] | str | bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(secret, payload), signature)
