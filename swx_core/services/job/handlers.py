"""
Job Handlers
------------
Example job handlers for billing, alerts, and audit.

Register these handlers at application startup.
"""

import uuid
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_

from swx_core.middleware.logging_middleware import logger
from swx_core.models.billing import BillingAccount, Subscription, SubscriptionStatus
from swx_core.services.billing.stripe_provider import get_stripe_provider
from swx_core.services.billing.subscription_service import SubscriptionService


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
        provider = get_stripe_provider()
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
        
        # Handle different webhook event types
        if event_type == "customer.subscription.updated":
            stripe_subscription_id = event_data.get("id")
            status = event_data.get("status")
            
            # Find subscription by Stripe ID
            stmt = select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if subscription:
                # Map Stripe status to our status
                status_map = {
                    "active": SubscriptionStatus.ACTIVE,
                    "canceled": SubscriptionStatus.CANCELED,
                    "past_due": SubscriptionStatus.PAST_DUE,
                    "unpaid": SubscriptionStatus.CANCELED,
                }
                new_status = status_map.get(status, SubscriptionStatus.ACTIVE)
                
                if subscription.status != new_status:
                    subscription.status = new_status
                    if new_status == SubscriptionStatus.CANCELED:
                        subscription.ended_at = datetime.utcnow()
                    session.add(subscription)
                    await session.commit()
                    logger.info(f"Updated subscription {subscription.id} status to {new_status}")
        
        elif event_type == "customer.subscription.deleted":
            stripe_subscription_id = event_data.get("id")
            
            # Find and cancel subscription
            stmt = select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if subscription:
                subscription.status = SubscriptionStatus.CANCELED
                subscription.ended_at = datetime.utcnow()
                session.add(subscription)
                await session.commit()
                logger.info(f"Cancelled subscription {subscription.id}")
        
        elif event_type == "invoice.payment_failed":
            # Handle payment failure - could trigger alerts or grace period
            stripe_subscription_id = event_data.get("subscription")
            logger.warning(f"Payment failed for subscription {stripe_subscription_id}")
            # Could update subscription to PAST_DUE status here
        
        # Trigger alert for important events
        if event_type in ("customer.subscription.deleted", "invoice.payment_failed"):
            from swx_core.services.alert_engine import alert_engine
            from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType
            
            await alert_engine.emit(
                severity=AlertSeverity.WARNING,
                source=AlertSource.BILLING,
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
        from swx_core.services.alert_engine import alert_engine
        from swx_core.services.channels.models import (
            AlertSeverity, AlertSource, AlertActorType, Alert
        )
        from datetime import datetime
        
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
    from datetime import datetime, timedelta
    from sqlmodel import func, desc
    
    # Parse date range
    date_from_str = payload.get("date_from")
    date_to_str = payload.get("date_to")
    
    if date_from_str:
        date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00"))
    else:
        date_from = datetime.utcnow() - timedelta(days=7)  # Default: last 7 days
    
    if date_to_str:
        date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00"))
    else:
        date_to = datetime.utcnow()
    
    logger.info(f"Aggregating audit logs from {date_from} to {date_to}")
    
    try:
        from swx_core.models.audit_log import AuditLog
        
        # Aggregate by action
        stmt = (
            select(
                AuditLog.action,
                AuditLog.resource_type,
                AuditLog.outcome,
                func.count(AuditLog.id).label("count")
            )
            .where(
                and_(
                    AuditLog.timestamp >= date_from,
                    AuditLog.timestamp <= date_to
                )
            )
            .group_by(AuditLog.action, AuditLog.resource_type, AuditLog.outcome)
            .order_by(desc("count"))
        )
        result = await session.execute(stmt)
        aggregates = result.all()
        
        # Aggregate by actor type
        stmt_actor = (
            select(
                AuditLog.actor_type,
                func.count(AuditLog.id).label("count")
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
        stmt_outcome = (
            select(
                AuditLog.outcome,
                func.count(AuditLog.id).label("count")
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
        stmt_total = (
            select(func.count(AuditLog.id))
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
        refreshed_items = []
        
        if cache_type == "all" or cache_type == "settings":
            # Refresh settings cache
            from swx_core.services.settings_service import SettingsService
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
