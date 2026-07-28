import hashlib
import hmac
import json
from typing import Any

from swx_core.services.llm.config_resolver import resolve_config


def _secret(secret: str) -> str:
    resolved_secret = resolve_config({"secret": secret}).get("secret") or ""
    return str(resolved_secret)


def _payload_bytes(payload: dict[str, Any] | str | bytes) -> bytes:
    if isinstance(payload, bytes):
        return payload
    elif isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_payload(secret: str, payload: dict[str, Any] | str | bytes) -> str:
    return hmac.new(_secret(secret).encode("utf-8"), _payload_bytes(payload), hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: dict[str, Any] | str | bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(secret, payload), signature)
