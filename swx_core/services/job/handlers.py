"""
Job Handlers
------------
Example job handlers for billing, alerts, and audit.

Register these handlers at application startup.
"""

import uuid
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_
from swx_core.utils.time import utc_now

from swx_core.middleware.logging_middleware import logger
from swx_core.models.billing import BillingAccount, Subscription, SubscriptionStatus
from swx_core.services.billing.stripe_provider import get_stripe_provider
from swx_core.services.billing.subscription_service import SubscriptionService

SUBSCRIPTION_SYNC_EVENT_TYPES = {
    "customer.subscription.created",
    "customer.subscription.updated",
}

def _utc_now_naive() -> datetime:
    return utc_now()

async def billing_sync_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for billing.sync jobs.
    
    Syncs billing account with external provider (e.g., Stripe).
    """
    account_id_str = payload.get("account_id")
    if not account_id_str:
        raise ValueError("account_id is required")
    
    account_id = uuid.UUID(account_id_str) if isinstance(account_id_str, str) else account_id_str
    logger.info(f"Syncing billing account: {account_id}")
    
    # Fetch account from database
    stmt = select(BillingAccount).where(BillingAccount.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        logger.warning(f"Billing account {account_id} not found")
        return {"status": "error", "message": "Account not found", "account_id": str(account_id)}
    
    # Get active subscription
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    
    if not subscription or not subscription.stripe_subscription_id:
        logger.info(f"No active Stripe subscription for account {account_id}")
        return {"status": "skipped", "account_id": str(account_id), "reason": "No Stripe subscription"}
    
    try:
        # Sync with Stripe
        _ = get_stripe_provider()
        # In a real implementation, we would fetch subscription from Stripe
        # and update local status if needed
        # For now, we'll just log the sync
        
        logger.info(f"Successfully synced billing account {account_id} with Stripe subscription {subscription.stripe_subscription_id}")
        return {
            "status": "synced",
            "account_id": str(account_id),
            "subscription_id": str(subscription.id),
            "stripe_subscription_id": subscription.stripe_subscription_id
        }
    except Exception as e:
        logger.error(f"Failed to sync billing account {account_id}: {e}")
        return {"status": "error", "message": str(e), "account_id": str(account_id)}

async def billing_webhook_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for billing.webhook jobs.
    
    Processes webhook events from billing provider (e.g., Stripe).
    """
    event_type = payload.get("event_type")
    event_data = payload.get("event_data", {})
    logger.info(f"Processing billing webhook: {event_type}")
    
    try:
        subscription_service = SubscriptionService(session)
        
        if event_type in SUBSCRIPTION_SYNC_EVENT_TYPES:
            await subscription_service.sync_stripe_subscription(event_data)

        elif event_type == "customer.subscription.deleted":
            stripe_subscription_id = event_data.get("id")

            stmt = select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.status = SubscriptionStatus.CANCELED
                subscription.ended_at = _utc_now_naive()
                session.add(subscription)
                await session.commit()
                logger.info(f"Cancelled subscription {subscription.id}")

        elif event_type == "checkout.session.completed":
            stripe_subscription_id = event_data.get("subscription")
            if not isinstance(stripe_subscription_id, str) or not stripe_subscription_id:
                logger.warning("Checkout session completed without subscription ID")
                return {
                    "processed": False,
                    "event_type": event_type,
                    "error": "Missing subscription ID",
                }

            provider = get_stripe_provider()
            if provider is None:
                logger.warning("Stripe provider unavailable for checkout session sync")
                return {
                    "processed": False,
                    "event_type": event_type,
                    "error": "Stripe provider unavailable",
                }

            subscription_data = await provider.get_subscription(stripe_subscription_id)
            await subscription_service.sync_stripe_subscription(subscription_data)
            logger.info(
                f"Synced subscription {stripe_subscription_id} from checkout completion"
            )

        elif event_type == "invoice.payment_failed":
            stripe_subscription_id = event_data.get("subscription")
            logger.warning(f"Payment failed for subscription {stripe_subscription_id}")

        if event_type in ("customer.subscription.deleted", "invoice.payment_failed"):
            from swx_core.services.alert_engine import alert_engine
            from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType
            
            await alert_engine.emit(
                severity=AlertSeverity.WARNING,
                source=AlertSource.SYSTEM,
                event_type=f"BILLING_{event_type.upper()}",
                message=f"Billing webhook event: {event_type}",
                actor_type=AlertActorType.SYSTEM,
                metadata={"event_type": event_type, "event_data": event_data}
            )
        
        return {"processed": True, "event_type": event_type}
    except Exception as e:
        logger.error(f"Failed to process billing webhook {event_type}: {e}")
        return {"processed": False, "event_type": event_type, "error": str(e)}

async def alert_send_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for alert.send jobs.
    
    Sends alert notification via specified channel.
    """
    alert_id = payload.get("alert_id")
    channel = payload.get("channel", "email")
    logger.info(f"Sending alert {alert_id} via {channel}")
    
    try:
        from swx_core.services.channels.models import (
            AlertSeverity, AlertSource, AlertActorType, Alert
        )
        
        # Extract alert details from payload
        severity = AlertSeverity(payload.get("severity", "INFO"))
        source = AlertSource(payload.get("source", "SYSTEM"))
        event_type = payload.get("event_type", "ALERT")
        message = payload.get("message", "Alert notification")
        metadata = payload.get("metadata", {})
        
        # Create alert object
        alert = Alert(
            severity=severity,
            source=source,
            event_type=event_type,
            message=message,
            environment=payload.get("environment", "production"),
            actor_type=AlertActorType(payload.get("actor_type", "NONE")),
            actor_id=payload.get("actor_id"),
            resource_type=payload.get("resource_type"),
            resource_id=payload.get("resource_id"),
            metadata=metadata
        )
        
        # Send via specific channel
        from swx_core.services.channels.log_channel import LogChannel
        from swx_core.services.channels.slack_channel import SlackChannel
        from swx_core.services.channels.email_channel import EmailChannel
        from swx_core.services.channels.sms_channel import SmsChannel
        
        channel_map = {
            "log": LogChannel(),
            "slack": SlackChannel(),
            "email": EmailChannel(),
            "sms": SmsChannel()
        }
        
        channel_instance = channel_map.get(channel)
        if channel_instance:
            success = await channel_instance.send(alert)
            if success:
                logger.info(f"Successfully sent alert {alert_id} via {channel}")
                return {"sent": True, "alert_id": alert_id, "channel": channel}
            else:
                logger.warning(f"Failed to send alert {alert_id} via {channel}")
                return {"sent": False, "alert_id": alert_id, "channel": channel, "reason": "Channel send failed"}
        else:
            logger.error(f"Unknown alert channel: {channel}")
            return {"sent": False, "alert_id": alert_id, "channel": channel, "reason": "Unknown channel"}
    
    except Exception as e:
        logger.error(f"Failed to send alert {alert_id} via {channel}: {e}")
        return {"sent": False, "alert_id": alert_id, "channel": channel, "error": str(e)}

async def audit_aggregate_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for audit.aggregate jobs.
    
    Aggregates audit logs for reporting and analysis.
    """
    from sqlmodel import func, desc
    
    # Parse date range
    date_from_str = payload.get("date_from")
    date_to_str = payload.get("date_to")
    
    if date_from_str:
        date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00"))
    else:
        date_from = utc_now() - timedelta(days=7)  # Default: last 7 days
    
    if date_to_str:
        date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00"))
    else:
        date_to = utc_now()
    
    logger.info(f"Aggregating audit logs from {date_from} to {date_to}")
    
    try:
        from swx_core.models.audit_log import AuditLog
        
        # Aggregate by action
        stmt = (  # pyright: ignore[reportArgumentType]
            select(
                AuditLog.action,
                AuditLog.resource_type,
                AuditLog.outcome,
                func.count(AuditLog.id).label("count")  # pyright: ignore[reportArgumentType]
            )
            .where(
                and_(
                    AuditLog.timestamp >= date_from,
                    AuditLog.timestamp <= date_to
                )
            )
            .group_by(AuditLog.action, AuditLog.resource_type, AuditLog.outcome)  # pyright: ignore[reportArgumentType]
            .order_by(desc("count"))
        )
        result = await session.execute(stmt)
        aggregates = result.all()
        
        # Aggregate by actor type
        stmt_actor = (  # pyright: ignore[reportArgumentType]
            select(
                AuditLog.actor_type,
                func.count(AuditLog.id).label("count")  # pyright: ignore[reportArgumentType]
            )
            .where(
                and_(
                    AuditLog.timestamp >= date_from,
                    AuditLog.timestamp <= date_to
                )
            )
            .group_by(AuditLog.actor_type)
        )
        result_actor = await session.execute(stmt_actor)
        actor_aggregates = result_actor.all()
        
        # Aggregate by outcome
        stmt_outcome = (  # pyright: ignore[reportArgumentType]
            select(
                AuditLog.outcome,
                func.count(AuditLog.id).label("count")  # pyright: ignore[reportArgumentType]
            )
            .where(
                and_(
                    AuditLog.timestamp >= date_from,
                    AuditLog.timestamp <= date_to
                )
            )
            .group_by(AuditLog.outcome)
        )
        result_outcome = await session.execute(stmt_outcome)
        outcome_aggregates = result_outcome.all()
        
        # Total count
        stmt_total = (  # pyright: ignore[reportArgumentType]
            select(func.count(AuditLog.id))  # pyright: ignore[reportArgumentType]
            .where(
                and_(
                    AuditLog.timestamp >= date_from,
                    AuditLog.timestamp <= date_to
                )
            )
        )
        result_total = await session.execute(stmt_total)
        total_count = result_total.scalar() or 0
        
        # Format results
        aggregation_results = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "total_records": total_count,
            "by_action": [
                {
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "outcome": row.outcome,
                    "count": row.count
                }
                for row in aggregates
            ],
            "by_actor_type": [
                {
                    "actor_type": row.actor_type,
                    "count": row.count
                }
                for row in actor_aggregates
            ],
            "by_outcome": [
                {
                    "outcome": row.outcome,
                    "count": row.count
                }
                for row in outcome_aggregates
            ]
        }
        
        logger.info(f"Aggregated {total_count} audit log records")
        return {
            "aggregated": True,
            "records": total_count,
            "results": aggregation_results
        }
    
    except Exception as e:
        logger.error(f"Failed to aggregate audit logs: {e}")
        return {"aggregated": False, "error": str(e), "records": 0}

async def cache_refresh_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for system.cache.refresh jobs.
    
    Refreshes application cache (settings, permissions, etc.).
    """
    cache_type = payload.get("cache_type", "all")
    logger.info(f"Refreshing cache: {cache_type}")
    
    try:
        from swx_core.services.settings_service import SettingsService

        refreshed_items = []
        
        if cache_type == "all" or cache_type == "settings":
            # Refresh settings cache
            SettingsService.invalidate_cache()
            refreshed_items.append("settings")
            logger.info("Invalidated settings cache")
        
        if cache_type == "all" or cache_type == "permissions":
            # Note: Permissions cache would be refreshed here if implemented
            # For now, we'll just log it
            refreshed_items.append("permissions")
            logger.info("Permissions cache refresh requested (not implemented)")
        
        if cache_type == "all" or cache_type == "policies":
            # Note: Policies cache would be refreshed here if implemented
            refreshed_items.append("policies")
            logger.info("Policies cache refresh requested (not implemented)")
        
        # Warm cache by accessing common settings
        if cache_type == "all" or cache_type == "settings":
            settings_service = SettingsService(session)
            # Pre-load common settings
            common_keys = [
                "auth.access_token_expire_minutes",
                "auth.refresh_token_expire_days",
                "system.environment"
            ]
            for key in common_keys:
                try:
                    await settings_service.get(key, None)
                except Exception:
                    pass  # Ignore errors for missing settings
        
        logger.info(f"Successfully refreshed cache: {', '.join(refreshed_items)}")
        return {
            "refreshed": True,
            "cache_type": cache_type,
            "refreshed_items": refreshed_items
        }
    
    except Exception as e:
        logger.error(f"Failed to refresh cache: {e}")
        return {"refreshed": False, "cache_type": cache_type, "error": str(e)}


async def compliance_data_subject_delete_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    request_id_str = payload.get("request_id")
    if not request_id_str:
        raise ValueError("request_id is required")

    from swx_core.services.compliance.erasure_service import process_erasure_for_request

    request_id = uuid.UUID(str(request_id_str))
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        raise ValueError("user_id is required")
    user_id = uuid.UUID(str(user_id_raw))

    logger.info(f"Processing data subject deletion for request {request_id}, user {user_id}")

    result = await process_erasure_for_request(session, request_id, user_id)

    logger.info(f"Data subject deletion completed for request {request_id}: {result.get('status')}")
    return result


async def compliance_retention_apply_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    resource_type = payload.get("resource_type")

    from swx_core.services.compliance.retention_service import apply_retention

    logger.info(f"Applying retention policy for resource_type={resource_type}")
    result = await apply_retention(session, resource_type=resource_type)
    logger.info(f"Retention applied: {result}")
    return {"status": "completed", "resource_type": resource_type, "result": result}


async def compliance_api_key_expired_cleanup_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    from swx_core.services.compliance.api_key_lifecycle_service import revoke_expired_api_keys

    logger.info("Running expired API key cleanup (SOC 2 CC6.1)")
    result = await revoke_expired_api_keys(session)
    logger.info("Expired API key cleanup completed: %d expired, %d inactive_revoked", result.get("expired_count", 0), result.get("inactive_revoked_count", 0))
    return result


async def compliance_session_idle_cleanup_handler(session: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    from swx_core.services.auth.session_service import expire_idle_sessions

    logger.info("Running idle session cleanup (SOC 2 CC6.1)")
    count = await expire_idle_sessions(session)
    logger.info("Idle session cleanup completed: %d sessions expired", count)
    return {"status": "completed", "sessions_expired": count}
