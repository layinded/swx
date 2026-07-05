"""Auto-accept team invitation during registration."""
from uuid import UUID
from swx_core.models.user import User


async def auto_accept_invitation(user: User, context: dict[str, str]) -> None:
    """Auto-accept team invitation when user registers with invitation token."""
    token = context.get("invitation_token")
    if not token:
        return None
    
    from swx_core.database.db import AsyncSessionLocal
    from swx_core.services.team_invitation_service import TeamInvitationService
    
    async with AsyncSessionLocal() as session:
        service = TeamInvitationService(session)
        try:
            token_str = str(UUID(token))
            await service.accept_invitation(token_str, user.id)
        except (ValueError, Exception):
            pass
    
    return None