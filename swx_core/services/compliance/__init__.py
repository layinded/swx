"""Compliance service package."""

from swx_core.services.compliance.compliance_report_service import (
    ComplianceFramework,
    ComplianceReport,
    SectionScore,
    generate_report,
    generate_all_reports,
)
from swx_core.services.compliance.erasure_service import (
    request_erasure,
    execute_erasure,
    cancel_erasure,
    get_erasure_certificate,
    list_erasure_certificates,
    process_erasure_for_request,
)
from swx_core.services.compliance.pii_encryption_service import (
    encrypt_email,
    decrypt_email,
    encrypt_full_name,
    decrypt_full_name,
    encrypt_user_pii,
    decrypt_user_pii,
    pii_encryption_enabled,
    should_encrypt_pii,
)

__all__ = [
    "ComplianceFramework",
    "ComplianceReport",
    "SectionScore",
    "generate_all_reports",
    "generate_report",
    "request_erasure",
    "execute_erasure",
    "cancel_erasure",
    "get_erasure_certificate",
    "list_erasure_certificates",
    "process_erasure_for_request",
    "encrypt_email",
    "decrypt_email",
    "encrypt_full_name",
    "decrypt_full_name",
    "encrypt_user_pii",
    "decrypt_user_pii",
    "pii_encryption_enabled",
    "should_encrypt_pii",
]
