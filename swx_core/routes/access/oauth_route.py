"""
OAuth Authentication Routes
----------------------
This module defines the API routes for OAuth-based authentication using Google and Facebook.

Features:
- Retrieve OAuth login URLs.
- Redirect users to OAuth providers (Google, Facebook).
- Handle OAuth callbacks to authenticate users.
- Fetch user details from third-party OAuth providers.
- Support for custom OAuth providers via configuration.

Methods:
- `get_oauth_urls()`: Returns OAuth login URLs dynamically based on configuration.
- `google_login()`: Redirects the user to Google OAuth authentication.
- `google_auth_callback()`: Handles Google OAuth callback and authenticates the user.
- `facebook_login()`: Redirects the user to Facebook OAuth authentication.
- `facebook_auth_callback()`: Handles Facebook OAuth callback and authenticates the user.
- `fetch_facebook_user_info()`: Retrieves user details from Facebook's Graph API.
"""

import logging
import secrets
import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from swx_core.config.settings import settings
from swx_core.config.social_settings import social_settings
from swx_core.controllers.auth_controller import login_social_user_controller

logger = logging.getLogger(__name__)
from swx_core.database.db import SessionDep
from swx_core.repositories.user_repository import (
    get_user_by_email,
    create_social_user,
)
from swx_core.utils.language_helper import translate

router = APIRouter(prefix="/oauth")
oauth = OAuth()

if social_settings.ENABLE_GOOGLE_LOGIN:
    oauth.register(
        name="google",
        client_id=social_settings.GOOGLE_CLIENT_ID,
        client_secret=social_settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if social_settings.ENABLE_FACEBOOK_LOGIN:
    oauth.register(
        name="facebook",
        client_id=social_settings.FACEBOOK_CLIENT_ID,
        client_secret=social_settings.FACEBOOK_CLIENT_SECRET,
        access_token_url="https://graph.facebook.com/v12.0/oauth/access_token",
        authorize_url="https://www.facebook.com/v12.0/dialog/oauth",
        client_kwargs={"scope": "email,public_profile"},
    )

from swx_core.core.oauth_providers import oauth_provider_settings

for provider_name, config in oauth_provider_settings.get_provider_configs().items():
    if provider_name not in oauth._clients:
        oauth.register(
            name=provider_name,
            **config.to_oauth_config(),
        )


@router.get("/urls")
async def get_oauth_urls():
    base_url = settings.BACKEND_HOST
    urls = {}

    if social_settings.ENABLE_SOCIAL_LOGIN:
        if social_settings.ENABLE_GOOGLE_LOGIN:
            urls["google"] = f"{base_url}/api/oauth/google"
        if social_settings.ENABLE_FACEBOOK_LOGIN:
            urls["facebook"] = f"{base_url}/api/oauth/facebook"

    for provider_name in oauth_provider_settings.get_provider_configs():
        urls[provider_name] = f"{base_url}/api/oauth/{provider_name}"

    return JSONResponse(urls)


@router.get("/google")
async def google_login(request: Request):
    try:
        if not social_settings.ENABLE_GOOGLE_LOGIN:
            raise HTTPException(status_code=400, detail=translate(request, "google_login_disabled"))

        redirect_uri = social_settings.GOOGLE_REDIRECT_URI
        if not redirect_uri:
            raise HTTPException(status_code=500, detail=translate(request, "google_redirect_uri_not_configured"))

        state = secrets.token_urlsafe(16)
        request.session["oauth_state"] = state
        return await oauth.google.authorize_redirect(request, redirect_uri, state=state)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Google login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=translate(request, "failed_to_initiate_google_login", error=str(e)))


@router.get("/google/callback")
async def google_auth_callback(request: Request, session: SessionDep):
    try:
        state = request.query_params.get("state")
        stored_state = request.session.get("oauth_state")
        if not stored_state or state != stored_state:
            return JSONResponse({"error": translate(request, "csrf_warning_state_mismatch")}, status_code=400)

        token = await oauth.google.authorize_access_token(request)
        if not token:
            return JSONResponse({"error": translate(request, "failed_to_fetch_google_token")}, status_code=400)

        user_info = token.get("userinfo", {})
        email = user_info.get("email")
        if not email:
            return JSONResponse({"error": translate(request, "google_account_missing_email")}, status_code=400)

        existing_user = await get_user_by_email(session=session, email=email)
        if not existing_user:
            existing_user = await create_social_user(session, email, user_info, "google")

        request.session.pop("oauth_state", None)
        return await login_social_user_controller(session, existing_user.email)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google auth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=translate(request, "google_auth_callback_failed", error=str(e)))


@router.get("/facebook")
async def facebook_login(request: Request):
    try:
        if not social_settings.ENABLE_FACEBOOK_LOGIN:
            raise HTTPException(status_code=400, detail=translate(request, "facebook_login_disabled"))

        redirect_uri = social_settings.FACEBOOK_REDIRECT_URI
        if not redirect_uri:
            raise HTTPException(status_code=500, detail=translate(request, "facebook_redirect_uri_not_configured"))

        return await oauth.facebook.authorize_redirect(request, redirect_uri)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Facebook login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=translate(request, "failed_to_initiate_facebook_login", error=str(e)))


async def fetch_facebook_user_info(access_token: str):
    user_info_url = "https://graph.facebook.com/me?fields=id,name,email"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(user_info_url, headers=headers)
            response.raise_for_status()
            user_data = response.json()

            if "error" in user_data:
                raise HTTPException(status_code=400, detail=f"Facebook API Error: {user_data['error']['message']}")

            return user_data

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Facebook API request failed: {str(e)}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect to Facebook API: {str(e)}")


@router.get("/facebook/callback")
async def facebook_auth_callback(request: Request, session: SessionDep):
    try:
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if not state or not code:
            raise HTTPException(status_code=400, detail=translate(request, "invalid_oauth_response"))

        token = await oauth.facebook.authorize_access_token(request)
        if not token:
            raise HTTPException(status_code=400, detail=translate(request, "failed_to_retrieve_facebook_token"))

        access_token = token.get("access_token")
        user_info = await fetch_facebook_user_info(access_token)
        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail=translate(request, "facebook_account_missing_email"))

        existing_user = await get_user_by_email(session=session, email=email)
        if not existing_user:
            existing_user = await create_social_user(session, email, user_info, "facebook")

        request.session.pop("oauth_state", None)
        return await login_social_user_controller(session, existing_user.email)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Facebook auth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=translate(request, "facebook_auth_callback_failed", error=str(e)))


@router.get("/{provider}")
async def provider_login(request: Request, provider: str):
    try:
        configs = oauth_provider_settings.get_provider_configs()

        if provider not in configs:
            raise HTTPException(status_code=400, detail=translate(request, f"{provider}_login_disabled"))

        config = configs[provider]
        redirect_uri = config.redirect_uri

        if not redirect_uri:
            raise HTTPException(
                status_code=500,
                detail=translate(request, f"{provider}_redirect_uri_not_configured"),
            )

        state = secrets.token_urlsafe(16)
        request.session["oauth_state"] = state

        client = getattr(oauth, provider)
        return await client.authorize_redirect(request, redirect_uri, state=state)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate {provider} login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initiate {provider} login: {str(e)}")


@router.get("/{provider}/callback")
async def provider_auth_callback(request: Request, session: SessionDep, provider: str):
    try:
        configs = oauth_provider_settings.get_provider_configs()

        if provider not in configs:
            raise HTTPException(status_code=400, detail=translate(request, f"{provider}_not_configured"))

        state = request.query_params.get("state")
        stored_state = request.session.get("oauth_state")
        if not stored_state or state != stored_state:
            return JSONResponse({"error": translate(request, "csrf_warning_state_mismatch")}, status_code=400)

        client = getattr(oauth, provider)
        token = await client.authorize_access_token(request)

        if not token:
            return JSONResponse({"error": translate(request, f"failed_to_fetch_{provider}_token")}, status_code=400)

        config = configs[provider]
        user_info_url = config.user_info_url

        if not user_info_url:
            user_info = token.get("userinfo", {})
        else:
            access_token = token.get("access_token")
            async with httpx.AsyncClient() as client:
                response = await client.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
                response.raise_for_status()
                user_info = response.json()

        email = user_info.get("email")
        if not email:
            return JSONResponse({"error": translate(request, f"{provider}_account_missing_email")}, status_code=400)

        existing_user = await get_user_by_email(session=session, email=email)
        if not existing_user:
            existing_user = await create_social_user(session, email, user_info, provider)

        request.session.pop("oauth_state", None)
        return await login_social_user_controller(session, existing_user.email)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{provider} auth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{provider} auth callback failed: {str(e)}")
