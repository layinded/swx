from fastapi import APIRouter

from swx_core.database.db import SessionDep
from swx_core.models.mfa import (
    MfaVerifyEnrollRequest,
    MfaDisableRequest,
    MfaStatusResponse,
    MfaEnrollResponse,
)
from swx_core.auth.user.dependencies import UserDep
from swx_core.services.auth.mfa_service import (
    enroll,
    verify_enrollment,
    disable,
    get_status,
    regenerate_recovery_codes,
)

router = APIRouter(prefix="/user/mfa", tags=["MFA"])


@router.post("/enroll", response_model=MfaEnrollResponse)
async def enroll_mfa(
    session: SessionDep,
    user: UserDep,
) -> MfaEnrollResponse:
    """
    Start MFA enrollment for the authenticated user.

    Returns a TOTP secret, QR code data URI, and one-time recovery codes.
    The user must verify enrollment with a valid TOTP code before MFA is active.
    """
    return await enroll(session, user.id)


@router.post("/verify-enrollment", response_model=MfaStatusResponse)
async def verify_mfa_enrollment(
    session: SessionDep,
    user: UserDep,
    data: MfaVerifyEnrollRequest,
) -> MfaStatusResponse:
    """
    Verify MFA enrollment by confirming the first TOTP code.

    Activates MFA for the user after successful verification.
    """
    return await verify_enrollment(session, user.id, data)


@router.get("/status", response_model=MfaStatusResponse)
async def get_mfa_status(
    session: SessionDep,
    user: UserDep,
) -> MfaStatusResponse:
    """Get the current MFA status for the authenticated user."""
    return await get_status(session, user.id)


@router.post("/disable", response_model=MfaStatusResponse)
async def disable_mfa(
    session: SessionDep,
    user: UserDep,
    data: MfaDisableRequest,
) -> MfaStatusResponse:
    """
    Disable MFA for the authenticated user.

    Requires a valid TOTP code or recovery code to confirm.
    """
    return await disable(session, user.id, data)


@router.post("/recovery-codes/regenerate", response_model=list[str])
async def regenerate_mfa_recovery_codes(
    session: SessionDep,
    user: UserDep,
    data: MfaDisableRequest,
) -> list[str]:
    """
    Regenerate MFA recovery codes.

    Requires a valid TOTP code or recovery code to confirm.
    Returns the new set of recovery codes.
    """
    return await regenerate_recovery_codes(session, user.id, data.code)