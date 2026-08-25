# pyright: reportExplicitAny=false, reportAny=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportArgumentType=false

import json
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func as sa_func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.erasure_certificate import ErasureCertificate
from swx_core.models.organization import Organization, OrganizationMember
from swx_core.models.team import Team
from swx_core.models.team_member import TeamMember
from swx_core.models.user import User
from swx_core.utils.time import utc_now


async def find_sole_owned_organizations(session: AsyncSession, user_id: UUID) -> list[Organization]:
    """Find organizations where the user is the sole owner (member count <= 1)."""
    member_count = (
        select(sa_func.count(OrganizationMember.id))
        .where(OrganizationMember.organization_id == Organization.id)
        .correlate(Organization)
        .scalar_subquery()
    )
    stmt = (
        select(Organization)
        .where(Organization.owner_id == user_id)
        .where(member_count <= 1)
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_users_due_for_erasure(session: AsyncSession) -> list[User]:
    """Find users past their GDPR grace period whose erasure is due."""
    now = utc_now()
    stmt = select(User).where(
        and_(
            User.is_active == False,  # noqa: E712
            User.gdpr_deleted_at != None,  # noqa: E711  # pyright: ignore[reportOptionalOperand]
            User.gdpr_deleted_at <= now,  # pyright: ignore[reportOptionalOperand]
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_sole_owned_teams(session: AsyncSession, user_id: UUID) -> list[Team]:
    """Find teams where the user is the sole owner (member count <= 1)."""
    member_count = (
        select(sa_func.count(TeamMember.id))
        .where(TeamMember.team_id == Team.id)
        .correlate(Team)
        .scalar_subquery()
    )
    stmt = (
        select(Team)
        .where(Team.owner_id == user_id)
        .where(member_count <= 1)
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_certificate(
    session: AsyncSession,
    user_id: UUID,
    erasure_type: str = "anonymize",
    request_id: UUID | None = None,
) -> ErasureCertificate:
    cert = ErasureCertificate(
        user_id=user_id,
        request_id=request_id,
        erasure_type=erasure_type,
        status="pending",
    )
    session.add(cert)
    await session.commit()
    await session.refresh(cert)
    return cert


async def get_certificate(session: AsyncSession, certificate_id: UUID) -> ErasureCertificate | None:
    return await session.get(ErasureCertificate, certificate_id)


async def list_certificates(
    session: AsyncSession,
    user_id: UUID | None = None,
    status: str | None = None,
) -> list[ErasureCertificate]:
    stmt = select(ErasureCertificate).order_by(ErasureCertificate.created_at.desc())
    if user_id:
        stmt = stmt.where(ErasureCertificate.user_id == user_id)
    if status:
        stmt = stmt.where(ErasureCertificate.status == status)
    return list((await session.execute(stmt)).scalars().all())


async def update_certificate(
    session: AsyncSession,
    certificate_id: UUID,
    status: str,
    tables_affected: list[str] | None = None,
    certificate_data: dict[str, str | list[str] | bool] | None = None,
    error_message: str | None = None,
    completed_at: datetime | None = None,
) -> ErasureCertificate | None:
    cert = await session.get(ErasureCertificate, certificate_id)
    if cert is None:
        return None
    cert.status = status
    if tables_affected is not None:
        cert.tables_affected = json.dumps(tables_affected)
    if certificate_data is not None:
        cert.certificate_data = json.dumps(certificate_data)
    if error_message is not None:
        cert.error_message = error_message
    if completed_at is not None:
        cert.completed_at = completed_at
    session.add(cert)
    await session.commit()
    await session.refresh(cert)
    return cert


async def mark_user_for_deletion(session: AsyncSession, user_id: UUID, grace_days: int = 30) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.is_active = False
    user.deactivated_at = utc_now()
    user.gdpr_deleted_at = utc_now() + timedelta(days=grace_days)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_email(session: AsyncSession, user_id: UUID) -> str | None:
    stmt = select(User.email).where(User.id == user_id)
    row = (await session.execute(stmt)).first()
    return row[0] if row else None


async def anonymize_user(session: AsyncSession, user_id: UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.email = f"erased_{user_id}@erased.invalid"
    user.full_name = "Erased User"
    user.hashed_password = ""
    user.auth_provider = "erased"
    user.provider_id = None
    user.avatar_url = None
    user.anonymous = True
    user.is_active = False
    user.deactivated_at = utc_now()
    user.gdpr_deleted_at = utc_now()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def cancel_deletion(session: AsyncSession, user_id: UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.is_active = True
    user.deactivated_at = None
    user.gdpr_deleted_at = None
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def hard_delete_user(session: AsyncSession, user_id: UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    await session.delete(user)
    await session.commit()
    return user


async def _anonymize_audit_logs(session: AsyncSession, user_id_str: str) -> int:
    from sqlalchemy import or_, update as sql_update
    from swx_core.models.audit_log import AuditLog

    actor_match = AuditLog.actor_id == user_id_str  # pyright: ignore[reportArgumentType]
    resource_match = AuditLog.resource_id == user_id_str  # pyright: ignore[reportArgumentType]
    stmt = (
        sql_update(AuditLog)
        .where(or_(actor_match, resource_match))  # pyright: ignore[reportArgumentType]
        .values(actor_id=None, ip_address=None, user_agent=None)
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue]


async def _delete_rows_by_column(
    session: AsyncSession,
    model_cls: type,
    filter_field: str,
    filter_value: object,
) -> str:
    """Delete rows matching filter_field == filter_value. Returns 'deleted:N'. No commit — caller batches."""
    from sqlmodel import delete as sql_delete

    col = getattr(model_cls, filter_field)
    stmt = sql_delete(model_cls).where(col == filter_value)  # pyright: ignore[reportArgumentType]
    result = await session.execute(stmt)
    count = int(result.rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue]
    return f"deleted:{count}"


async def _anonymize_column_by_user_id(
    session: AsyncSession,
    model_cls: type,
    filter_field: str,
    user_id: UUID,
) -> str:
    """SET filter_field = NULL where filter_field == user_id. Returns 'anonymized:N'. No commit — caller batches."""
    from sqlalchemy import update as sql_update

    col = getattr(model_cls, filter_field)
    stmt = (
        sql_update(model_cls)
        .where(col == user_id)  # pyright: ignore[reportArgumentType]
        .values(**{filter_field: None})
    )
    result = await session.execute(stmt)
    count = int(result.rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue]
    return f"anonymized:{count}"


async def delete_user_related_data(session: AsyncSession, user_id: UUID, user_email: str) -> dict[str, str]:
    """Per-table erasure policy.

    Hard delete: tables where no analytics/audit value is retained.
    Anonymize: tables where PII is cleared but the row persists for audit/analytics.
    Retain: tables that serve as compliance proof (erasure_certificates).

    All deletes/anonymizes are batched into a single commit at the end.
    Conversation messages are deleted before their parent conversations (FK order).
    """
    from swx_core.models.social_account import SocialAccount
    from swx_core.models.mfa import MfaRecoveryCode
    from swx_core.models.refresh_token import RefreshToken
    from swx_core.models.sso_session import SSOSession
    from swx_core.models.device import Device
    from swx_core.models.notification import Notification
    from swx_core.models.notification_preference import NotificationPreference
    from swx_core.models.api_key_scope import ApiKey
    from swx_core.models.webhook_endpoint import WebhookEndpoint
    from swx_core.models.onboarding import OnboardingStep
    from swx_core.models.conversation import Conversation
    from swx_core.models.conversation_message import ConversationMessage
    from swx_core.models.safety_check import SafetyCheck
    from swx_core.models.data_export import DataExport
    from swx_core.models.data_import import DataImport
    from swx_core.models.consent import UserConsent
    from swx_core.models.compliance_audit import DataSubjectRequest
    from swx_core.models.user_role import UserRole
    from swx_core.models.team_member import TeamMember
    from swx_core.models.team_invitation import TeamInvitation
    from swx_core.models.organization import Organization, OrganizationMember
    from swx_core.models.organization_invitation import OrganizationInvitation
    from swx_core.models.referral import ReferralCode, ReferralEvent
    from swx_core.models.flag_evaluation import FlagEvaluation
    from swx_core.models.team import Team
    from swx_core.models.ledger import LedgerEntry

    results: dict[str, str] = {}

    # Step 1: Delete conversation messages BEFORE conversations (FK constraint order)
    try:
        conv_ids = list((await session.execute(
            select(Conversation.id).where(Conversation.user_id == user_id)
        )).scalars().all())
        if conv_ids:
            from sqlmodel import delete as sql_delete
            msg_result = await session.execute(
                sql_delete(ConversationMessage).where(
                    ConversationMessage.conversation_id.in_(conv_ids)  # pyright: ignore[reportAttributeAccessIssue]
                )
            )
            count = int(msg_result.rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue]
            results["swx_conversation_messages"] = f"deleted:{count}"
        else:
            results["swx_conversation_messages"] = "deleted:0"
    except Exception as e:
        results["swx_conversation_messages"] = f"error:{e}"

    # Step 2: Hard-delete all related tables (order doesn't matter for non-FK tables)
    hard_delete_spec: list[tuple[str, type, str, object]] = [
        ("swx_social_accounts", SocialAccount, "user_id", user_id),
        ("swx_mfa_recovery_codes", MfaRecoveryCode, "user_id", user_id),
        ("swx_refresh_tokens", RefreshToken, "user_email", user_email),
        ("swx_sso_sessions", SSOSession, "user_id", user_id),
        ("swx_devices", Device, "user_id", user_id),
        ("swx_notifications", Notification, "user_id", user_id),
        ("swx_notification_preferences", NotificationPreference, "user_id", user_id),
        ("swx_api_keys", ApiKey, "user_id", user_id),
        ("swx_webhook_endpoints", WebhookEndpoint, "user_id", user_id),
        ("swx_onboarding_steps", OnboardingStep, "user_id", user_id),
        ("swx_conversations", Conversation, "user_id", user_id),
        ("swx_safety_checks", SafetyCheck, "user_id", user_id),
        ("swx_data_exports", DataExport, "user_id", user_id),
        ("swx_data_imports", DataImport, "user_id", user_id),
        ("swx_user_consents", UserConsent, "user_id", user_id),
        ("swx_data_subject_requests", DataSubjectRequest, "user_id", user_id),
        ("swx_user_roles", UserRole, "user_id", user_id),
        ("swx_team_members", TeamMember, "user_id", user_id),
        ("swx_team_invitations", TeamInvitation, "inviter_id", user_id),
        ("swx_organization_members", OrganizationMember, "user_id", user_id),
        ("swx_organization_invitations", OrganizationInvitation, "inviter_id", user_id),
        ("swx_referral_codes", ReferralCode, "user_id", user_id),
        ("swx_referral_events", ReferralEvent, "referred_user_id", user_id),
    ]

    for table_name, model_cls, filter_field, filter_value in hard_delete_spec:
        try:
            results[table_name] = await _delete_rows_by_column(session, model_cls, filter_field, filter_value)
        except Exception as e:
            results[table_name] = f"error:{e}"

    # Step 3: Anonymize audit logs (no commit — batched)
    try:
        audit_count = await _anonymize_audit_logs(session, str(user_id))
        results["swx_audit_logs"] = f"anonymized:{audit_count}"
    except Exception as e:
        results["swx_audit_logs"] = f"error:{e}"

    # Step 4: Anonymize PII columns in analytics/audit tables
    anonymize_spec: list[tuple[str, type, str]] = [
        ("swx_flag_evaluations", FlagEvaluation, "user_id"),
        ("swx_teams", Team, "owner_id"),
        ("swx_organizations", Organization, "owner_id"),
        ("swx_ledger_entries", LedgerEntry, "created_by"),
    ]

    for table_name, model_cls, filter_field in anonymize_spec:
        try:
            results[table_name] = await _anonymize_column_by_user_id(session, model_cls, filter_field, user_id)
        except Exception as e:
            results[table_name] = f"error:{e}"

    # Step 5: Single commit for all operations
    await session.commit()

    return results