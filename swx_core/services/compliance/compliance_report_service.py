"""Compliance Readiness Report Service
--------------------------------------
Generates scored readiness reports for GDPR, HIPAA, CCPA, DORA, and FERPA
based on audit log data and system configuration.

Each framework has sections scored from audit evidence.  The score reflects
*evidence availability*, not certification status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from swx_core.models.audit_log import AuditLog
from swx_core.services.settings_service import SettingsService
from swx_core.middleware.logging_middleware import logger


class ComplianceFramework(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    CCPA = "ccpa"
    DORA = "dora"
    FERPA = "ferpa"


@dataclass(frozen=True)
class SectionScore:
    """Score for a single compliance section."""
    section: str
    score: float  # 0–100
    evidence_count: int
    details: str = ""


@dataclass
class ComplianceReport:
    """Aggregated readiness report for one framework."""
    framework: ComplianceFramework
    overall_score: float
    sections: list[SectionScore] = field(default_factory=list)

    @property
    def readiness_level(self) -> str:
        if self.overall_score >= 80:
            return "ready"
        if self.overall_score >= 50:
            return "partial"
        return "insufficient"


_FRAMEWORK_SECTIONS: dict[ComplianceFramework, list[dict[str, Any]]] = {
    ComplianceFramework.GDPR: [
        {"section": "data_consent", "actions": ["consent.grant", "consent.revoke", "consent.withdraw"], "weight": 25},
        {"section": "data_access", "actions": ["data.export", "data.access_request"], "weight": 20},
        {"section": "data_deletion", "actions": ["data.delete", "data.anonymize", "retention.apply"], "weight": 20},
        {"section": "breach_notification", "actions": ["breach.detect", "breach.notify", "alert.send"], "weight": 20},
        {"section": "audit_trail", "actions": ["audit.read", "audit.export", "policy.read"], "weight": 15},
    ],
    ComplianceFramework.HIPAA: [
        {"section": "access_control", "actions": ["auth.login", "auth.mfa_enable", "rbac.assign"], "weight": 25},
        {"section": "audit_logging", "actions": ["audit.read", "audit.export", "data.access_request"], "weight": 20},
        {"section": "encryption", "actions": ["encryption.rotate_key", "encryption.config_update"], "weight": 20},
        {"section": "data_retention", "actions": ["retention.apply", "data.anonymize", "data.delete"], "weight": 20},
        {"section": "breach_response", "actions": ["breach.detect", "breach.notify", "alert.send"], "weight": 15},
    ],
    ComplianceFramework.CCPA: [
        {"section": "data_access", "actions": ["data.export", "data.access_request"], "weight": 30},
        {"section": "data_deletion", "actions": ["data.delete", "data.anonymize"], "weight": 30},
        {"section": "opt_out", "actions": ["consent.revoke", "consent.withdraw"], "weight": 20},
        {"section": "audit_trail", "actions": ["audit.read", "audit.export"], "weight": 20},
    ],
    ComplianceFramework.DORA: [
        {"section": "risk_management", "actions": ["policy.create", "policy.update", "rbac.assign"], "weight": 25},
        {"section": "incident_response", "actions": ["breach.detect", "breach.notify", "alert.send"], "weight": 25},
        {"section": "audit_trail", "actions": ["audit.read", "audit.export"], "weight": 25},
        {"section": "data_protection", "actions": ["encryption.rotate_key", "retention.apply"], "weight": 25},
    ],
    ComplianceFramework.FERPA: [
        {"section": "consent", "actions": ["consent.grant", "consent.revoke"], "weight": 30},
        {"section": "data_access", "actions": ["data.export", "data.access_request"], "weight": 25},
        {"section": "audit_trail", "actions": ["audit.read", "audit.export"], "weight": 25},
        {"section": "data_retention", "actions": ["retention.apply", "data.delete"], "weight": 20},
    ],
}


async def _count_audit_events(session: AsyncSession, actions: list[str], days: int = 90) -> int:
    """Count audit log entries matching *actions* within the last *days*."""
    from swx_core.utils.time import utc_now
    from datetime import timedelta

    cutoff = utc_now() - timedelta(days=days)
    stmt = select(func.count()).select_from(AuditLog).where(
        AuditLog.action.in_(actions),
        AuditLog.timestamp >= cutoff,
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def generate_report(
    session: AsyncSession,
    framework: ComplianceFramework,
    days: int = 90,
) -> ComplianceReport:
    """Generate a compliance readiness report for the given framework.

    Args:
        session: Async DB session.
        framework: The compliance framework to assess.
        days: Look-back window in days (default 90).

    Returns:
        A ``ComplianceReport`` with section scores and overall readiness.
    """
    sections_config = _FRAMEWORK_SECTIONS[framework]
    section_scores: list[SectionScore] = []
    weighted_total = 0.0

    for config in sections_config:
        evidence_count = await _count_audit_events(session, config["actions"], days)
        score = min(100.0, evidence_count * 10)  # 10 points per evidence, cap 100
        section_scores.append(SectionScore(
            section=config["section"],
            score=score,
            evidence_count=evidence_count,
            details=f"{evidence_count} audit event(s) in last {days} days",
        ))
        weighted_total += score * config["weight"]

    total_weight = sum(c["weight"] for c in sections_config)
    overall_score = round(weighted_total / total_weight, 1) if total_weight else 0.0

    report = ComplianceReport(
        framework=framework,
        overall_score=overall_score,
        sections=section_scores,
    )
    logger.info("Compliance report: %s readiness=%s score=%.1f", framework.value, report.readiness_level, overall_score)
    return report


async def generate_all_reports(session: AsyncSession, days: int = 90) -> dict[str, ComplianceReport]:
    """Generate readiness reports for all supported frameworks."""
    reports: dict[str, ComplianceReport] = {}
    for framework in ComplianceFramework:
        reports[framework.value] = await generate_report(session, framework, days)
    return reports