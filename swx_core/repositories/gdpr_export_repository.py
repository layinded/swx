# pyright: reportExplicitAny=false, reportAny=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportArgumentType=false

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.user import User
from swx_core.models.social_account import SocialAccount
from swx_core.models.mfa import MfaRecoveryCode
from swx_core.models.conversation import Conversation
from swx_core.models.conversation_message import ConversationMessage
from swx_core.models.consent import UserConsent
from swx_core.models.notification import Notification
from swx_core.models.notification_preference import NotificationPreference
from swx_core.models.api_key_scope import ApiKey
from swx_core.models.webhook_endpoint import WebhookEndpoint
from swx_core.models.device import Device
from swx_core.models.data_export import DataExport
from swx_core.models.data_import import DataImport
from swx_core.models.user_role import UserRole
from swx_core.models.team_member import TeamMember
from swx_core.models.organization import OrganizationMember
from swx_core.models.referral import ReferralCode, ReferralEvent
from swx_core.models.onboarding import OnboardingStep
from swx_core.models.flag_evaluation import FlagEvaluation
from swx_core.models.audit_log import AuditLog


async def get_user_profile(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_social_accounts(session: AsyncSession, user_id: UUID) -> list[SocialAccount]:
    stmt = select(SocialAccount).where(SocialAccount.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_conversations(session: AsyncSession, user_id: UUID) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_conversation_messages(session: AsyncSession, conversation_ids: list[UUID]) -> list[ConversationMessage]:
    if not conversation_ids:
        return []
    stmt = select(ConversationMessage).where(ConversationMessage.conversation_id.in_(conversation_ids))  # pyright: ignore[reportAttributeAccessIssue]
    return list((await session.execute(stmt)).scalars().all())


async def get_user_consents(session: AsyncSession, user_id: UUID) -> list[UserConsent]:
    stmt = select(UserConsent).where(UserConsent.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_notifications(session: AsyncSession, user_id: UUID) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_notification_preferences(session: AsyncSession, user_id: UUID) -> list[NotificationPreference]:
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_api_keys(session: AsyncSession, user_id: UUID) -> list[ApiKey]:
    stmt = select(ApiKey).where(ApiKey.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_webhook_endpoints(session: AsyncSession, user_id: UUID) -> list[WebhookEndpoint]:
    stmt = select(WebhookEndpoint).where(WebhookEndpoint.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_devices(session: AsyncSession, user_id: UUID) -> list[Device]:
    stmt = select(Device).where(Device.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_exports(session: AsyncSession, user_id: UUID) -> list[DataExport]:
    stmt = select(DataExport).where(DataExport.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_imports(session: AsyncSession, user_id: UUID) -> list[DataImport]:
    stmt = select(DataImport).where(DataImport.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_roles(session: AsyncSession, user_id: UUID) -> list[UserRole]:
    stmt = select(UserRole).where(UserRole.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_team_memberships(session: AsyncSession, user_id: UUID) -> list[TeamMember]:
    stmt = select(TeamMember).where(TeamMember.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_org_memberships(session: AsyncSession, user_id: UUID) -> list[OrganizationMember]:
    stmt = select(OrganizationMember).where(OrganizationMember.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_referral_codes(session: AsyncSession, user_id: UUID) -> list[ReferralCode]:
    stmt = select(ReferralCode).where(ReferralCode.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_referral_events(session: AsyncSession, user_id: UUID) -> list[ReferralEvent]:
    stmt = select(ReferralEvent).where(ReferralEvent.referred_user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_onboarding_steps(session: AsyncSession, user_id: UUID) -> list[OnboardingStep]:
    stmt = select(OnboardingStep).where(OnboardingStep.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_flag_evaluations(session: AsyncSession, user_id: UUID) -> list[FlagEvaluation]:
    stmt = select(FlagEvaluation).where(FlagEvaluation.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_user_audit_logs(session: AsyncSession, user_id_str: str) -> list[AuditLog]:
    from sqlalchemy import or_

    stmt = select(AuditLog).where(
        or_(AuditLog.actor_id == user_id_str, AuditLog.resource_id == user_id_str)  # pyright: ignore[reportArgumentType]
    )
    return list((await session.execute(stmt)).scalars().all())