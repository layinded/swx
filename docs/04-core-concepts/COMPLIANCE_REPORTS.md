# Compliance Reports

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Frameworks](#supported-frameworks)
3. [Scoring Model](#scoring-model)
4. [API Reference](#api-reference)
5. [Usage Examples](#usage-examples)

---

## Overview

The **Compliance Report Service** (`swx_core/services/compliance/compliance_report_service.py`) generates scored readiness reports for GDPR, HIPAA, CCPA, DORA, and FERPA based on audit log data and system configuration. Each framework has sections scored from audit evidence, with the score reflecting **evidence availability**, not certification status.

Key features:

- **Five frameworks** — GDPR, HIPAA, CCPA, DORA, FERPA
- **Weighted section scoring** — each section has a weight (percentage of total score)
- **Evidence-based** — scores are computed from audit log entries in the look-back window
- **Readiness levels** — ready (≥80), partial (≥50), insufficient (<50)

---

## Supported Frameworks

| Framework | Sections |
|---|---|
| **GDPR** | data_consent, data_access, data_deletion, breach_notification, audit_trail |
| **HIPAA** | access_control, audit_logging, encryption, data_retention, breach_response |
| **CCPA** | data_access, data_deletion, opt_out, audit_trail |
| **DORA** | risk_management, incident_response, audit_trail, data_protection |
| **FERPA** | consent, data_access, audit_trail, data_retention |

---

## Scoring Model

Each section is scored based on audit evidence count:

- **10 points per evidence entry**, capped at 100 per section
- **Weighted average** across sections produces the overall score
- **Readiness level**: `ready` (≥80), `partial` (≥50), `insufficient` (<50)

```
section_score = min(100, evidence_count * 10)
overall_score = sum(section_score * weight) / sum(weights)
```

### Example

| Section | Weight | Evidence Count | Score |
|---|---|---|---|
| data_consent | 25% | 8 | 80 |
| data_access | 20% | 3 | 30 |
| data_deletion | 20% | 12 | 100 |
| breach_notification | 20% | 0 | 0 |
| audit_trail | 15% | 5 | 50 |
| **Overall** | | | **51.5 (partial)** |

---

## API Reference

### `generate_report(session, framework, days=90) -> ComplianceReport`

Generate a compliance readiness report for the given framework.

| Parameter | Type | Description |
|---|---|---|
| `session` | `AsyncSession` | Database session |
| `framework` | `ComplianceFramework` | One of `GDPR`, `HIPAA`, `CCPA`, `DORA`, `FERPA` |
| `days` | `int` | Look-back window in days (default: 90) |

### `generate_all_reports(session, days=90) -> dict[str, ComplianceReport]`

Generate readiness reports for all supported frameworks.

### `ComplianceReport`

| Field | Type | Description |
|---|---|---|
| `framework` | `ComplianceFramework` | The assessed framework |
| `overall_score` | `float` | Weighted average score (0–100) |
| `sections` | `list[SectionScore]` | Per-section scores |
| `readiness_level` | `str` | `"ready"`, `"partial"`, or `"insufficient"` |

### `SectionScore`

| Field | Type | Description |
|---|---|---|
| `section` | `str` | Section name (e.g., `"data_consent"`) |
| `score` | `float` | Section score (0–100) |
| `evidence_count` | `int` | Number of matching audit events |
| `details` | `str` | Human-readable description |

---

## Usage Examples

### Generate a Single Report

```python
from swx_core.services.compliance.compliance_report_service import generate_report, ComplianceFramework

report = await generate_report(session, ComplianceFramework.GDPR, days=90)
print(f"GDPR readiness: {report.readiness_level} (score: {report.overall_score})")

for section in report.sections:
    print(f"  {section.section}: {section.score}/100 ({section.evidence_count} events)")
```

### Generate All Reports

```python
from swx_core.services.compliance.compliance_report_service import generate_all_reports

reports = await generate_all_reports(session, days=90)
for framework, report in reports.items():
    print(f"{framework}: {report.readiness_level} ({report.overall_score})")
```

### Admin API Endpoint

```python
from fastapi import APIRouter, Depends
from swx_core.services.compliance.compliance_report_service import generate_report, ComplianceFramework

router = APIRouter(prefix="/admin/compliance", tags=["compliance"])

@router.get("/reports/{framework}")
async def get_compliance_report(
    framework: ComplianceFramework,
    days: int = 90,
    admin: AdminUserDep = Depends(get_current_admin_user),
    session: SessionDep = Depends(get_session),
):
    report = await generate_report(session, framework, days)
    return {
        "framework": report.framework.value,
        "overall_score": report.overall_score,
        "readiness_level": report.readiness_level,
        "sections": [
            {"section": s.section, "score": s.score, "evidence_count": s.evidence_count}
            for s in report.sections
        ],
    }
```