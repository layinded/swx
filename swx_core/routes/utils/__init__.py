from fastapi import APIRouter

from .health_route import router as health_router
from .language_route import router as language_router

router = APIRouter()
router.include_router(health_router)
router.include_router(language_router)
