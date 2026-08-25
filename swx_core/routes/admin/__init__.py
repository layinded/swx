# pyright: reportMissingImports=false

from fastapi import APIRouter

from .api_key_route import router as api_key_router
from .audit_route import router as audit_router
from .auth_route import router as auth_router
from .billing_currency_route import router as billing_currency_router
from .billing_feature_route import router as billing_feature_router
from .billing_plan_route import router as billing_plan_router
from .compliance_route import router as compliance_router
from .consent_route import router as consent_router
from .conversation_route import router as conversation_router
from .data_transfer_route import router as data_transfer_router
from .feature_flag_route import router as feature_flag_router
from .job_route import router as job_router
from .ledger_route import router as ledger_router
from .llm_route import router as llm_router
from .notification_provider_route import router as notification_provider_router
from .organization_route import router as organization_router
from .permission_route import router as permission_router
from .policy_route import router as policy_router
from .role_route import router as role_router
from .safety_route import router as safety_router
from .settings_route import router as settings_router
from .sso_route import router as sso_router
from .status_route import router as status_router
from .team_route import router as team_router
from .user_role_route import router as user_role_router
from .user_route import router as user_router
from .wallet_adjustment_route import router as wallet_adjustment_router
from .webhook_route import router as webhook_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(billing_feature_router)
router.include_router(billing_plan_router)
router.include_router(billing_currency_router)
router.include_router(job_router)
router.include_router(permission_router)
router.include_router(policy_router)
router.include_router(role_router)
router.include_router(settings_router)
router.include_router(team_router)
router.include_router(user_role_router)
router.include_router(user_router)
router.include_router(audit_router)
router.include_router(consent_router)
router.include_router(compliance_router)
router.include_router(ledger_router)
router.include_router(llm_router)
router.include_router(notification_provider_router)
router.include_router(organization_router)
router.include_router(api_key_router)
router.include_router(webhook_router)
router.include_router(conversation_router)
router.include_router(safety_router)
router.include_router(sso_router)
router.include_router(status_router)
router.include_router(data_transfer_router)
router.include_router(feature_flag_router)
router.include_router(wallet_adjustment_router)
