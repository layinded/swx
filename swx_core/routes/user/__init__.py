from fastapi import APIRouter

from .billing_route import router as billing_router
from .consent_route import router as consent_router
from .llm_route import router as llm_router
from .organization_route import router as organization_router
from .user_route import router as user_router

router = APIRouter()
router.include_router(billing_router)
router.include_router(consent_router)
router.include_router(llm_router)
router.include_router(organization_router)
router.include_router(user_router)
