# pyright: reportExplicitAny=false, reportAny=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.erasure_certificate import ErasureCertificatePublic
from swx_core.models.user import User
from swx_core.repositories import erasure_repository
from swx_core.utils.time import utc_now


async def request_erasure(
    session: AsyncSession,
    user_id: UUID,
    request_id: UUID | None = None,
) -> ErasureCertificatePublic:
    """Start the erasure process for a user.

    Checks sole-owner guard first: if the user is the sole owner of any
    organization or team, erasure is blocked until ownership is transferred.
    Then deactivates the account, sets gdpr_deleted_at, revokes tokens,
    and invalidates auth cache.
    """
    sole_owned = await _check_sole_owner(session, user_id)
    if sole_owned:
        names = [f"{o.__class__.__name__}: {o.name}" for o in sole_owned]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot erase user: sole owner of {', '.join(names)}. Transfer ownership before erasing.",
        )

    erasure_type = "anonymize" if settings.GDPR_ANONYMIZE_ON_DELETE else "delete"
    cert = await erasure_repository.create_certificate(
        session=session,
        user_id=user_id,
        erasure_type=erasure_type,
        request_id=request_id,
    )

    user = await erasure_repository.mark_user_for_deletion(
        session=session,
        user_id=user_id,
        grace_days=settings.GDPR_DELETION_GRACE_DAYS,
    )

    if user is None:
        await erasure_repository.update_certificate(
            session, cert.id, status="failed", error_message="User not found",
        )
        raise HTTPException(status_code=404, detail="User not found")

    await _revoke_auth_session(session, user)

    deletion_at = user.gdpr_deleted_at.isoformat() if user.gdpr_deleted_at else None

    await event_bus.dispatch("gdpr.erasure_requested", payload={
        "user_id": str(user_id),
        "certificate_id": str(cert.id),
        "erasure_type": cert.erasure_type,
        "deletion_at": deletion_at,
    })

    logger.info(f"Erasure requested for user {user_id}, certificate {cert.id}, deletion_at={deletion_at}")

    return ErasureCertificatePublic.model_validate(cert)


async def execute_erasure(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    """Execute the actual erasure for a user whose grace period has expired.

    Checks sole-owner guard first. Then applies per-table erasure policy:
    - swx_users: anonymize PII (or hard delete) based on GDPR_ANONYMIZE_ON_DELETE
    - 23 related tables: hard delete (tokens, sessions, social accounts, etc.)
    - Audit logs: anonymize (clear actor_id, ip_address, user_agent)
    - Flag evaluations: anonymize (clear user_id, keep analytics row)
    - Erasure certificates: retained as compliance proof
    """
    sole_owned = await _check_sole_owner(session, user_id)
    if sole_owned:
        names = [f"{o.__class__.__name__}: {o.name}" for o in sole_owned]
        return {"status": "blocked", "reason": f"Sole owner of {', '.join(names)}. Transfer ownership before erasing."}

    erasure_type = "anonymize" if settings.GDPR_ANONYMIZE_ON_DELETE else "delete"
    cert = await erasure_repository.create_certificate(
        session=session,
        user_id=user_id,
        erasure_type=erasure_type,
    )

    tables_erased: list[str] = []
    errors: list[str] = []

    user_email = await erasure_repository.get_user_email(session, user_id) or ""

    if settings.GDPR_ANONYMIZE_ON_DELETE:
        user = await erasure_repository.anonymize_user(session=session, user_id=user_id)
        if user is None:
            await erasure_repository.update_certificate(
                session, cert.id, status="failed", error_message="User not found",
            )
            return {"status": "failed", "error": "User not found"}
        tables_erased.append("swx_users")
    else:
        user = await erasure_repository.hard_delete_user(session=session, user_id=user_id)
        if user is None:
            await erasure_repository.update_certificate(
                session, cert.id, status="failed", error_message="User not found",
            )
            return {"status": "failed", "error": "User not found"}
        tables_erased.append("swx_users")

    related_results = await erasure_repository.delete_user_related_data(
        session, user_id, user_email,
    )
    for table_name, result in related_results.items():
        if result.startswith("error:"):
            errors.append(f"{table_name}: {result}")
        else:
            tables_erased.append(table_name)

    await _revoke_auth_session(session, user)

    certificate_data = {
        "erasure_type": erasure_type,
        "tables_erased": tables_erased,
        "errors": errors,
        "anonymized_pii": settings.GDPR_ANONYMIZE_ON_DELETE,
    }

    await erasure_repository.update_certificate(
        session=session,
        certificate_id=cert.id,
        status="completed",
        tables_affected=tables_erased,
        certificate_data=certificate_data,
        completed_at=utc_now(),
    )

    await event_bus.dispatch("gdpr.erasure_completed", payload={
        "user_id": str(user_id),
        "certificate_id": str(cert.id),
        "erasure_type": erasure_type,
        "tables_erased": tables_erased,
    })

    logger.info(f"Erasure completed for user {user_id}, certificate {cert.id}")

    return {
        "status": "completed",
        "certificate_id": str(cert.id),
        "erasure_type": erasure_type,
        "tables_erased": tables_erased,
    }


async def cancel_erasure(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    """Cancel a pending erasure during the grace period.

    Restores the user account to active status and clears gdpr_deleted_at.
    """
    user = await erasure_repository.cancel_deletion(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await event_bus.dispatch("gdpr.erasure_cancelled", payload={"user_id": str(user_id)})

    logger.info(f"Erasure cancelled for user {user_id}")
    return {"status": "restored", "user_id": str(user_id)}


async def get_erasure_certificate(session: AsyncSession, certificate_id: UUID) -> ErasureCertificatePublic | None:
    cert = await erasure_repository.get_certificate(session, certificate_id)
    if cert is None:
        return None
    return ErasureCertificatePublic.model_validate(cert)


async def list_erasure_certificates(
    session: AsyncSession,
    user_id: UUID | None = None,
    status: str | None = None,
) -> list[ErasureCertificatePublic]:
    certs = await erasure_repository.list_certificates(session, user_id=user_id, status=status)
    return [ErasureCertificatePublic.model_validate(c) for c in certs]


async def process_erasure_for_request(
    session: AsyncSession,
    request_id: UUID,
    user_id: UUID,
) -> dict[str, object]:
    """Called by the compliance_data_subject_delete_handler to execute erasure.

    Bridges the DSR system and the erasure system without re-enqueuing.
    """
    from swx_core.repositories import compliance_audit_repository

    request = await compliance_audit_repository.get_data_subject_request(session, request_id)
    if request is None or not request.verified:
        return {"status": "skipped", "reason": "Request not found or not verified"}

    result = await execute_erasure(session, user_id)

    await compliance_audit_repository.update_data_subject_request(
        session, request_id,
        {"status": "completed", "completed_at": utc_now()},
    )

    return result


async def _revoke_auth_session(session: AsyncSession, user: User) -> None:
    """Revoke refresh tokens and invalidate auth cache for a user.

    Called at erasure request time (deactivation) and at execution time.
    """
    from swx_core.auth.auth_cache import invalidate_user_cache, invalidate_user_permissions
    from swx_core.security.refresh_token_service import revoke_all_tokens

    try:
        await revoke_all_tokens(session, user.email)
        logger.info(f"Revoked all refresh tokens for {user.email}")
    except Exception as e:
        logger.warning(f"Failed to revoke tokens for {user.email}: {e}")

    try:
        await invalidate_user_cache(str(user.id), user.email)
        await invalidate_user_permissions(str(user.id))
        logger.info(f"Invalidated auth cache for user {user.id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate auth cache for user {user.id}: {e}")


async def _check_sole_owner(session: AsyncSession, user_id: UUID) -> list[object]:
    """Check if user is the sole owner of any organization or team.

    Returns a list of Organization/Team objects where the user is sole owner.
    If the list is non-empty, erasure must be blocked until ownership is transferred.
    """
    sole_owned: list[object] = []

    sole_orgs = await erasure_repository.find_sole_owned_organizations(session, user_id)
    sole_owned.extend(sole_orgs)

    sole_teams = await erasure_repository.find_sole_owned_teams(session, user_id)
    sole_owned.extend(sole_teams)

    return sole_owned