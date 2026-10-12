from fastapi import APIRouter, Request
from fastapi.security import OAuth2PasswordRequestForm

from swx_core.database.db import SessionDep
from swx_core.models.token import Token
from swx_core.models.mfa import MfaChallengeRequest, MfaStepUpRequest, MfaStepUpResponse
from swx_core.controllers.auth_controller import verify_mfa_challenge_controller, step_up_mfa_controller
from swx_core.auth.user.dependencies import UserDep
from swx_core.utils.rate_limit import rate_limit_by_ip

router = APIRouter(prefix="/auth/mfa")


@router.post("/verify", response_model=Token)
@rate_limit_by_ip(max_requests=10, window_seconds=60, action="mfa_verify")
async def verify_mfa_challenge(
    session: SessionDep,
    data: MfaChallengeRequest,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> Token:
    """
    Verify an MFA challenge after successful password authentication.

    When login returns `mfa_required=True`, the client must call this
    endpoint with the `mfa_token` and a valid TOTP or recovery code
    to obtain real access and refresh tokens.

    Args:
        session: The database session.
        data: The MFA challenge request (mfa_token + code).
        request: The HTTP request object.

    Returns:
        Token: Full access and refresh tokens upon successful verification.
    """
    return await verify_mfa_challenge_controller(
        session, data.mfa_token, data.code, request
    )


@router.post("/step-up", response_model=MfaStepUpResponse)
@rate_limit_by_ip(max_requests=5, window_seconds=60, action="mfa_step_up")
async def step_up_mfa(
    session: SessionDep,
    user: UserDep,
    data: MfaStepUpRequest,
) -> MfaStepUpResponse:
    """
    Step-up authentication for sensitive operations.

    Authenticated users call this with their TOTP or recovery code
    to obtain a short-lived step-up token. Pass the token in the
    `X-Step-Up-Token` header on subsequent sensitive requests.

    Returns:
        MfaStepUpResponse: step_up_token and expires_in (seconds).
    """
    return await step_up_mfa_controller(session, user.id, data.code)