from typing import Any
from fastapi import Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.token import Token, TokenRefreshRequest
from swx_core.services.admin_auth_service import (
    login_admin_service,
    refresh_admin_token_service,
    logout_admin_service,
)


async def login_admin_controller(
    session: AsyncSession, form_data: OAuth2PasswordRequestForm, request: Request
) -> Token:
    return await login_admin_service(session, form_data, request)


async def refresh_admin_token_controller(
    session: AsyncSession, request_data: TokenRefreshRequest, request: Request
) -> Token:
    return await refresh_admin_token_service(session, request_data, request)


async def logout_admin_controller(
    session: AsyncSession, request_data: TokenRefreshRequest, request: Request
) -> dict[str, Any]:
    return await logout_admin_service(session, request_data, request)
