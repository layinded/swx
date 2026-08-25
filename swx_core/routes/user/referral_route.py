from fastapi import APIRouter

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import referral_controller
from swx_core.database.db import SessionDep

router = APIRouter(prefix="/user/referrals", tags=["user-referrals"])


@router.get("/code", response_model=dict[str, object])
async def get_referral_code(session: SessionDep, current_user: UserDep) -> dict[str, object]:
    return await referral_controller.get_referral_code_controller(session, current_user.id)


@router.get("/history", response_model=list[dict[str, object]])
async def list_referral_history(session: SessionDep, current_user: UserDep) -> list[dict[str, object]]:
    return await referral_controller.list_referrals_controller(session, current_user.id)