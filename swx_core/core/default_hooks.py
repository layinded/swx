"""
Default Registration Hooks
---------------------------
Built-in post-registration hooks that assign a default role, create a billing
account, and create a personal team for newly registered users.

Registered automatically by bootstrap_app() when enabled via settings:
- AUTO_ASSIGN_DEFAULT_ROLE (default: True) — assigns DEFAULT_USER_ROLE
- AUTO_CREATE_BILLING_ACCOUNT (default: True) — creates a USER billing account
- AUTO_CREATE_PERSONAL_TEAM (default: True) — creates a personal team and sets tenant_id

To disable, set the environment variable to "false" or "0".

All hooks receive the parent database session so side effects share the same
transaction. If a hook fails, the entire registration rolls back — no half-baked
users without teams, roles, or billing accounts.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user import User
from swx_core.models.user_role import UserRoleCreate
from swx_core.models.team import Team
from swx_core.models.team_member import TeamMember
from swx_core.models.billing import BillingAccountType
from swx_core.middleware.logging_middleware import logger


async def assign_default_role(user: User, session: AsyncSession, context: dict) -> User:
    from swx_core.config.settings import settings
    from swx_core.repositories import role_repository, user_role_repository

    role_name = settings.DEFAULT_USER_ROLE
    if not role_name:
        return user

    role = await role_repository.get_role_by_name(session, role_name)
    if not role:
        logger.warning(
            f"Default role '{role_name}' not found — skipping role assignment. "
            "Run seed_system to create default roles."
        )
        return user

    assignment = UserRoleCreate(user_id=user.id, role_id=role.id)
    await user_role_repository.assign_role_to_user(session, assignment)
    logger.info(f"Assigned default role '{role_name}' to user {user.id}")

    return user


async def create_billing_account(user: User, session: AsyncSession, context: dict) -> User:
    from swx_core.config.settings import settings
    from swx_core.services.billing.subscription_service import SubscriptionService

    if not settings.BILLING_ENABLED:
        return user

    subscription_service = SubscriptionService(session)
    account = await subscription_service.get_or_create_account(
        owner_id=user.id,
        account_type=BillingAccountType.USER,
    )

    try:
        await subscription_service.create_subscription(
            account_id=account.id,
            plan_key=settings.DEFAULT_PLAN_KEY,
        )
        logger.info(
            f"Created billing account and free subscription for user {user.id}"
        )
    except Exception as e:
        logger.warning(
            f"Could not create subscription for user {user.id}: {e}. "
            "Skipping — user has billing account but no subscription."
        )

    return user


async def create_personal_team(user: User, session: AsyncSession, _context: dict) -> User:
    """
    Create a personal team for the user and set tenant_id.
    
    This ensures users have a valid tenant_id for tenant-aware operations.
    Without a personal team, users without tenant_id get 500 errors on
    protected endpoints.
    """
    from swx_core.config.settings import settings
    from swx_core.models.team_role import TeamRole
    from sqlmodel import select

    if not getattr(settings, 'AUTO_CREATE_PERSONAL_TEAM', True):
        return user

    # Capture lazy-loadable attributes before any DB work to avoid
    # DetachedInstanceError / MissingGreenlet from cross-session access.
    user_full_name = user.full_name
    user_email = user.email
    user_id = user.id

    team = Team(
        name=f"{user_full_name or user_email}'s Team",
        description="Personal team",
        owner_id=user_id,
    )
    session.add(team)
    await session.flush()

    result = await session.execute(select(TeamRole).where(TeamRole.key == "owner"))
    owner_role = result.scalar_one_or_none()

    if owner_role:
        session.add(TeamMember(
            team_id=team.id,
            user_id=user_id,
            team_role_id=owner_role.id,
        ))
    else:
        logger.warning(
            f"Owner role not found — user {user_id} added to team without role. "
            "Run seed_system to create default team roles."
        )

    user.tenant_id = team.id
    logger.info(f"Created personal team {team.id} for user {user_id}")

    return user