from fastapi import APIRouter

from .auth_route import router as auth_router
from .billing_feature_route import router as billing_feature_router
from .billing_plan_route import router as billing_plan_router
from .billing_currency_route import router as billing_currency_router
from .job_route import router as job_router
from .permission_route import router as permission_router
from .policy_route import router as policy_router
from .role_route import router as role_router
from .settings_route import router as settings_router
from .team_route import router as team_router
from .user_role_route import router as user_role_router
from .user_route import router as user_router
from .audit_route import router as audit_router
from .consent_route import router as consent_router
from .ledger_route import router as ledger_router
from .llm_route import router as llm_router
from .organization_route import router as organization_router

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
router.include_router(ledger_router)
router.include_router(llm_router)
router.include_router(organization_router)
