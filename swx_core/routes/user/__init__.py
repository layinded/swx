# pyright: reportMissingImports=false

from fastapi import APIRouter

from .billing_route import router as billing_router
from .consent_route import router as consent_router
from .gdpr_route import router as gdpr_router
from .llm_route import router as llm_router
from .notification_route import router as notification_router
from .organization_route import router as organization_router
from .user_route import router as user_router
from .api_key_route import router as api_key_router
from .webhook_route import router as webhook_router
from .conversation_route import router as conversation_router
from .safety_route import router as safety_router
from .sso_route import router as sso_router
from .status_route import router as status_router
from .data_transfer_route import router as data_transfer_router
from .feature_flag_route import router as feature_flag_router

router = APIRouter()
router.include_router(billing_router)
router.include_router(consent_router)
router.include_router(gdpr_router)
router.include_router(llm_router)
router.include_router(notification_router)
router.include_router(organization_router)
router.include_router(user_router)
router.include_router(api_key_router)
router.include_router(webhook_router)
router.include_router(conversation_router)
router.include_router(safety_router)
router.include_router(sso_router)
router.include_router(status_router)
router.include_router(data_transfer_router)
router.include_router(feature_flag_router)
