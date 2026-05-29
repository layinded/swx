from fastapi import APIRouter

from .auth_route import router as auth_router
from .oauth_route import router as oauth_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(oauth_router)
