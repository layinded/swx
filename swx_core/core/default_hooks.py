"""
Default Registration Hooks
---------------------------
Built-in post-registration hooks that assign a default role and billing
account to newly registered users.

These hooks are registered automatically by bootstrap_app() when the
corresponding settings are enabled:
- AUTO_ASSIGN_DEFAULT_ROLE (default: True) — assigns DEFAULT_USER_ROLE
- AUTO_CREATE_BILLING_ACCOUNT (default: True) — creates a USER billing account

To disable, set the environment variable to "false" or "0".
"""

from swx_core.models.user import User, UserCreate
from swx_core.models.user_role import UserRoleCreate
from swx_core.models.billing import BillingAccountType
from swx_core.middleware.logging_middleware import logger


async def assign_default_role(user: User, context: dict) -> User:
    """
    Post-register hook that assigns the default role to a new user.

    Looks up DEFAULT_USER_ROLE from settings and creates a UserRole assignment.
    Silently skips if the role doesn't exist (e.g., seed_system hasn't run yet).
    """
    from swx_core.config.settings import settings
    from swx_core.repositories import role_repository, user_role_repository
    from swx_core.database.db import AsyncSessionLocal

    role_name = settings.DEFAULT_USER_ROLE
    if not role_name:
        return user

    session = context.get("session")
    if not session:
        async with AsyncSessionLocal() as session:
            await _assign_role(session, user, role_name)
            await session.commit()
        return user

    await _assign_role(session, user, role_name)
    return user


async def _assign_role(session, user: User, role_name: str) -> None:
    from swx_core.repositories import role_repository, user_role_repository

    role = await role_repository.get_role_by_name(session, role_name)
    if not role:
        logger.warning(
            f"Default role '{role_name}' not found — skipping role assignment. "
            "Run seed_system to create default roles."
        )
        return

    assignment = UserRoleCreate(user_id=user.id, role_id=role.id)
    await user_role_repository.assign_role_to_user(session, assignment)
    logger.info(f"Assigned default role '{role_name}' to user {user.id}")


async def create_billing_account(user: User, context: dict) -> User:
    """
    Post-register hook that creates a billing account and free-tier subscription.

    Creates a USER billing account and subscribes it to the DEFAULT_PLAN_KEY plan.
    Silently skips if billing is not enabled or the plan doesn't exist.
    """
    from swx_core.config.settings import settings

    if not settings.BILLING_ENABLED:
        return user

    session = context.get("session")
    if not session:
        from swx_core.database.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await _create_billing(session, user)
            await session.commit()
        return user

    await _create_billing(session, user)
    return user


async def _create_billing(session, user: User) -> None:
    from swx_core.config.settings import settings
    from swx_core.services.billing.subscription_service import SubscriptionService

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