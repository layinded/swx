# pyright: reportExplicitAny=false, reportAny=false

import base64
import io
import secrets
from datetime import timedelta
from uuid import UUID

import pyotp
import qrcode
from anyio import to_thread
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.models.mfa import (
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
    MfaVerifyEnrollRequest,
    MfaStepUpResponse,
)
from swx_core.repositories import mfa_repository
from swx_core.security.encryption import encrypt_value, decrypt_value
from swx_core.security.refresh_token_service import create_mfa_token
from swx_core.events.dispatcher import event_bus
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RECOVERY_CODE_COUNT = 10


def _generate_totp_secret() -> str:
    return pyotp.random_base32()


def _build_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=settings.PROJECT_NAME
    )


def _generate_qr_code_data_uri(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # pyright: ignore[reportCallIssue]
    buf.seek(0)
    return f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}"


def _generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    return [secrets.token_urlsafe(8).upper() for _ in range(count)]


async def _hash_code(code: str) -> str:
    return await to_thread.run_sync(pwd_context.hash, code)


async def _verify_code(hashed: str, code: str) -> bool:
    return await to_thread.run_sync(pwd_context.verify, code, hashed)


async def enroll(session: AsyncSession, user_id: UUID) -> MfaEnrollResponse:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    secret = _generate_totp_secret()
    encrypted_secret = encrypt_value(secret)

    await mfa_repository.set_mfa_secret(session, user_id, encrypted_secret)

    uri = _build_provisioning_uri(secret, user.email)
    qr_code_uri = _generate_qr_code_data_uri(uri)

    recovery_codes_plain = _generate_recovery_codes()
    recovery_hashes = [await _hash_code(code) for code in recovery_codes_plain]
    await mfa_repository.create_recovery_codes(session, user_id, recovery_hashes)

    logger.info(f"MFA enrollment initiated for user {user_id}")

    await event_bus.dispatch("mfa.enrollment_initiated", payload={"user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.AUTH_MFA_ENABLED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
        context={"phase": "enrollment_initiated"},
    )

    return MfaEnrollResponse(
        secret=secret,
        qr_code_uri=qr_code_uri,
        recovery_codes=recovery_codes_plain,
    )


async def verify_enrollment(session: AsyncSession, user_id: UUID, data: MfaVerifyEnrollRequest) -> MfaStatusResponse:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if not user.mfa_secret:
        raise ValueError("MFA not enrolled. Call enroll first.")

    decrypted_secret = decrypt_value(user.mfa_secret)
    totp = pyotp.TOTP(decrypted_secret)

    if not totp.verify(data.code, valid_window=1):
        raise ValueError("Invalid TOTP code")

    await mfa_repository.update_mfa_status(session, user_id, enabled=True, secret=user.mfa_secret)
    await mfa_repository.set_mfa_verified_at(session, user_id)

    logger.info(f"MFA enrollment verified for user {user_id}")
    await event_bus.dispatch("mfa.enrollment_verified", payload={"user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.AUTH_MFA_ENABLED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
        context={"phase": "enrollment_verified"},
    )

    return MfaStatusResponse(mfa_enabled=True, mfa_verified_at=user.mfa_verified_at)


async def verify_challenge(session: AsyncSession, user_id: UUID, code: str) -> bool:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None or not user.mfa_secret:
        return False

    decrypted_secret = decrypt_value(user.mfa_secret)
    totp = pyotp.TOTP(decrypted_secret)
    return totp.verify(code, valid_window=1)


async def verify_recovery_code(session: AsyncSession, user_id: UUID, recovery_code: str) -> bool:
    unused_codes = await mfa_repository.get_unused_recovery_codes(session, user_id)
    for code_entry in unused_codes:
        if await _verify_code(code_entry.code_hash, recovery_code):
            await mfa_repository.mark_recovery_code_used(session, code_entry.id)
            logger.info(f"Recovery code used for user {user_id}")
            await event_bus.dispatch("mfa.recovery_code_used", payload={"user_id": str(user_id), "code_id": str(code_entry.id)})
            return True
    return False


async def disable(session: AsyncSession, user_id: UUID, data: MfaDisableRequest) -> MfaStatusResponse:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if not user.mfa_enabled:
        raise ValueError("MFA is not enabled")

    if not await verify_challenge(session, user_id, data.code):
        if not await verify_recovery_code(session, user_id, data.code):
            raise ValueError("Invalid verification code")

    await mfa_repository.update_mfa_status(session, user_id, enabled=False)
    await mfa_repository.delete_all_recovery_codes(session, user_id)

    logger.info(f"MFA disabled for user {user_id}")
    await event_bus.dispatch("mfa.disabled", payload={"user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.AUTH_MFA_DISABLED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
    )

    return MfaStatusResponse(mfa_enabled=False, mfa_verified_at=None)


async def get_status(session: AsyncSession, user_id: UUID) -> MfaStatusResponse:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return MfaStatusResponse(mfa_enabled=user.mfa_enabled, mfa_verified_at=user.mfa_verified_at)


async def regenerate_recovery_codes(session: AsyncSession, user_id: UUID, code: str) -> list[str]:
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if not user.mfa_enabled:
        raise ValueError("MFA is not enabled")

    if not await verify_challenge(session, user_id, code):
        if not await verify_recovery_code(session, user_id, code):
            raise ValueError("Invalid verification code")

    await mfa_repository.delete_all_recovery_codes(session, user_id)

    new_codes = _generate_recovery_codes()
    new_hashes = [await _hash_code(c) for c in new_codes]
    await mfa_repository.create_recovery_codes(session, user_id, new_hashes)

    logger.info(f"Recovery codes regenerated for user {user_id}")
    await event_bus.dispatch("mfa.recovery_codes_regenerated", payload={"user_id": str(user_id)})
    return new_codes


async def step_up(session: AsyncSession, user_id: UUID, code: str) -> MfaStepUpResponse:
    """Verify MFA for a step-up authentication request.

    Called by authenticated users before performing sensitive operations.
    Returns a short-lived step-up token that the `RecentMfaDep` dependency validates.
    """
    user = await mfa_repository.get_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if not user.mfa_enabled:
        raise ValueError("MFA is not enabled")

    if not await verify_challenge(session, user_id, code):
        if not await verify_recovery_code(session, user_id, code):
            raise ValueError("Invalid verification code")

    step_up_token = create_mfa_token(
        email=user.email,
        user_id=str(user_id),
        expires_delta=timedelta(minutes=settings.MFA_CHALLENGE_EXPIRE_MINUTES),
    )

    logger.info(f"MFA step-up authentication verified for user {user_id}")
    await event_bus.dispatch("mfa.step_up_verified", payload={"user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.AUTH_MFA_CHALLENGE_SUCCESS,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
        context={"auth_method": "mfa_step_up"},
    )

    return MfaStepUpResponse(
        step_up_token=step_up_token,
        expires_in=settings.MFA_CHALLENGE_EXPIRE_MINUTES * 60,
    )