from fastapi import APIRouter

from swx_core.database.db import SessionDep
from swx_core.models.social_account import SocialAccountPublic, SocialAccountUnlinkRequest
from swx_core.auth.user.dependencies import UserDep
from swx_core.services.auth.account_linking_service import (
    get_linked_accounts,
    unlink_social_account,
)

router = APIRouter(prefix="/user/accounts", tags=["Account Linking"])


@router.get("/linked", response_model=list[SocialAccountPublic])
async def list_linked_accounts(
    session: SessionDep,
    user: UserDep,
) -> list[SocialAccountPublic]:
    """List all social accounts linked to the authenticated user."""
    return await get_linked_accounts(session, user.id)


@router.delete("/unlink")
async def unlink_account(
    session: SessionDep,
    user: UserDep,
    data: SocialAccountUnlinkRequest,
) -> dict[str, bool]:
    """
    Unlink a social provider from the authenticated user's account.

    Cannot unlink if it's the only authentication method and no password is set.
    """
    return await unlink_social_account(session, user.id, data.provider)