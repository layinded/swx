from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets

from anyio import to_thread
from passlib.context import CryptContext

from swx_core.config.settings import settings
from swx_core.utils.time import utc_now


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True, slots=True)
class OtpEntry:
    hashed_code: str
    expires_at: datetime
    attempts: int
    sent_at: datetime


class OtpResendCooldownError(Exception):
    pass


_OTP_CACHE: dict[str, OtpEntry] = {}


def _is_bypass_enabled() -> bool:
    return settings.OTP_BYPASS_FOR_TESTING and settings.ENVIRONMENT in {"local", "development"}


def _generate_code() -> str:
    if _is_bypass_enabled():
        return "1".zfill(settings.OTP_LENGTH)
    maximum: int = 10**settings.OTP_LENGTH
    return str(secrets.randbelow(maximum)).zfill(settings.OTP_LENGTH)


async def generate_otp(email: str) -> str:
    code = _generate_code()
    now = utc_now()
    hashed_code = await to_thread.run_sync(pwd_context.hash, code)
    _OTP_CACHE[email.casefold()] = OtpEntry(
        hashed_code=hashed_code,
        expires_at=now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        attempts=0,
        sent_at=now,
    )
    return code


async def verify_otp(email: str, code: str) -> bool:
    cache_key = email.casefold()
    entry = _OTP_CACHE.get(cache_key)
    if entry is None:
        return False
    now = utc_now()
    if entry.expires_at <= now or entry.attempts >= settings.OTP_MAX_ATTEMPTS:
        _OTP_CACHE.pop(cache_key, None)
        return False
    verified = await to_thread.run_sync(pwd_context.verify, code, entry.hashed_code)
    if verified:
        _OTP_CACHE.pop(cache_key, None)
        return True
    updated_entry = OtpEntry(
        hashed_code=entry.hashed_code,
        expires_at=entry.expires_at,
        attempts=entry.attempts + 1,
        sent_at=entry.sent_at,
    )
    _OTP_CACHE[cache_key] = updated_entry
    if updated_entry.attempts >= settings.OTP_MAX_ATTEMPTS:
        _OTP_CACHE.pop(cache_key, None)
    return False


async def resend_otp(email: str) -> str:
    cache_key = email.casefold()
    entry = _OTP_CACHE.get(cache_key)
    if entry is not None:
        elapsed_seconds = int((utc_now() - entry.sent_at).total_seconds())
        if elapsed_seconds < settings.OTP_RESEND_COOLDOWN_SECONDS:
            raise OtpResendCooldownError("OTP resend cooldown active")
    return await generate_otp(email)
