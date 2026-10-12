"""Auto-accept team invitation during registration."""
from uuid import UUID

from swx_core.models.user import User
from swx_core.middleware.logging_middleware import logger


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
        except ValueError:
            logger.warning("Invalid invitation token format for user %s", user.id)
        except Exception:
            logger.exception("Failed to auto-accept invitation for user %s", user.id)

    return None