"""
OAuth Authentication Routes
----------------------
OAuth 2.0 Authorization Code Flow with PKCE and Backend-for-Frontend (BFF) pattern.

Security Features:
- PKCE (RFC 7636) for all OAuth flows - mandatory per RFC 9700
- State parameter for CSRF protection
- HTTP-only cookies for token storage (XSS resistant)
- Redirect-based callback handling

Flow:
1. Frontend redirects to /oauth/{provider}
2. Backend generates PKCE challenge, stores verifier in session
3. User authenticates with OAuth provider
4. Provider redirects to /oauth/{provider}/callback
5. Backend exchanges code + PKCE verifier for tokens
6. Backend sets HTTP-only cookies and redirects to frontend
"""

import hashlib
import base64
import logging
import secrets
import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse

from swx_core.config.settings import settings
from swx_core.config.social_settings import social_settings
from swx_core.controllers.auth_controller import login_social_user_controller
from swx_core.database.db import SessionDep
from swx_core.repositories.user_repository import get_user_by_email, create_social_user
from swx_core.utils.language_helper import translate
from swx_core.services.settings_helper import get_token_expiration
from swx_core.core.oauth_providers import oauth_provider_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth")
oauth = OAuth()

FRONTEND_CALLBACK_URL = f"{settings.FRONTEND_HOST}/auth/callback"


def generate_pkce_verifier() -> str:
    """Generate PKCE code verifier (43-128 chars, URL-safe)."""
    return secrets.token_urlsafe(43)


def generate_pkce_challenge(verifier: str) -> str:
    """Generate PKCE code challenge using S256 method."""
    sha256 = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(sha256).decode().rstrip('=')


def error_redirect(error: str) -> RedirectResponse:
    """Create redirect response with error parameter."""
    return RedirectResponse(url=f"{FRONTEND_CALLBACK_URL}?error={error}", status_code=302)


async def set_auth_cookies(
    response: RedirectResponse,
    access_token: str,
    refresh_token: str | None,
    access_token_max_age: int,
    refresh_token_max_age: int,
) -> RedirectResponse:
    """Set HTTP-only auth cookies on response."""
    if not refresh_token:
        return response

    secure = settings.COOKIE_SECURE and settings.ENVIRONMENT != "local"
    samesite = settings.COOKIE_SAMESITE
    domain = settings.COOKIE_DOMAIN

    response.set_cookie(
        key=settings.COOKIE_ACCESS_TOKEN_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=access_token_max_age,
        path="/",
        domain=domain,
    )
    response.set_cookie(
        key=settings.COOKIE_REFRESH_TOKEN_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=refresh_token_max_age,
        path="/api",
        domain=domain,
    )
    return response


async def validate_oauth_state(request: Request) -> str | None:
    """Validate OAuth state parameter. Returns error message or None if valid."""
    state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state")
    if not stored_state or state != stored_state:
        return "csrf_mismatch"
    return None


def store_pkce_session(request: Request) -> tuple[str, str, str]:
    """Generate and store PKCE verifier in session. Returns (verifier, challenge, state)."""
    code_verifier = generate_pkce_verifier()
    code_challenge = generate_pkce_challenge(code_verifier)
    state = secrets.token_urlsafe(16)

    request.session["oauth_state"] = state
    request.session["code_verifier"] = code_verifier

    return code_verifier, code_challenge, state


def clear_oauth_session(request: Request) -> None:
    """Clear OAuth-related session data."""
    request.session.pop("oauth_state", None)
    request.session.pop("code_verifier", None)


async def complete_oauth_login(
    session: SessionDep,
    email: str,
    provider: str,
    is_new_user: bool,
) -> RedirectResponse:
    """Complete OAuth login by generating tokens and setting cookies."""
    auth_token = await login_social_user_controller(
        session,
        email,
        event_context={"provider": provider, "is_new_user": is_new_user}
    )

    access_expires = await get_token_expiration(session, "access")
    refresh_expires = await get_token_expiration(session, "refresh")

    response = RedirectResponse(url=FRONTEND_CALLBACK_URL, status_code=302)
    return await set_auth_cookies(
        response=response,
        access_token=auth_token.access_token,
        refresh_token=auth_token.refresh_token,
        access_token_max_age=int(access_expires.total_seconds()),
        refresh_token_max_age=int(refresh_expires.total_seconds()),
    )


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

        code_verifier, code_challenge, state = store_pkce_session(request)

        return await oauth.google.authorize_redirect(
            request,
            redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Google login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=translate(request, "failed_to_initiate_google_login", error=str(e)))


@router.get("/google/callback")
async def google_auth_callback(request: Request, session: SessionDep):
    try:
        if error := await validate_oauth_state(request):
            return error_redirect(error)

        code_verifier = request.session.get("code_verifier")
        token = await oauth.google.authorize_access_token(request, code_verifier=code_verifier)
        if not token:
            return error_redirect("token_fetch_failed")

        user_info = token.get("userinfo", {})
        email = user_info.get("email")
        if not email:
            return error_redirect("missing_email")

        existing_user = await get_user_by_email(session=session, email=email)
        is_new_user = existing_user is None
        if is_new_user:
            existing_user = await create_social_user(session, email, user_info, "google")

        clear_oauth_session(request)
        return await complete_oauth_login(session, existing_user.email, "google", is_new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google auth callback failed: {e}", exc_info=True)
        return error_redirect(str(e))


@router.get("/facebook")
async def facebook_login(request: Request):
    try:
        if not social_settings.ENABLE_FACEBOOK_LOGIN:
            raise HTTPException(status_code=400, detail=translate(request, "facebook_login_disabled"))

        redirect_uri = social_settings.FACEBOOK_REDIRECT_URI
        if not redirect_uri:
            raise HTTPException(status_code=500, detail=translate(request, "facebook_redirect_uri_not_configured"))

        code_verifier, code_challenge, state = store_pkce_session(request)

        return await oauth.facebook.authorize_redirect(
            request,
            redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
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
        if error := await validate_oauth_state(request):
            return error_redirect(error)

        code_verifier = request.session.get("code_verifier")
        token = await oauth.facebook.authorize_access_token(request, code_verifier=code_verifier)
        if not token:
            return error_redirect("token_fetch_failed")

        access_token = token.get("access_token")
        user_info = await fetch_facebook_user_info(access_token)
        email = user_info.get("email")
        if not email:
            return error_redirect("missing_email")

        existing_user = await get_user_by_email(session=session, email=email)
        is_new_user = existing_user is None
        if is_new_user:
            existing_user = await create_social_user(session, email, user_info, "facebook")

        clear_oauth_session(request)
        return await complete_oauth_login(session, existing_user.email, "facebook", is_new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Facebook auth callback failed: {e}", exc_info=True)
        return error_redirect(str(e))


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

        code_verifier, code_challenge, state = store_pkce_session(request)

        client = getattr(oauth, provider)
        return await client.authorize_redirect(
            request,
            redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
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

        if error := await validate_oauth_state(request):
            return error_redirect(error)

        code_verifier = request.session.get("code_verifier")
        client = getattr(oauth, provider)
        token = await client.authorize_access_token(request, code_verifier=code_verifier)

        if not token:
            return error_redirect("token_fetch_failed")

        config = configs[provider]
        user_info_url = config.user_info_url

        if not user_info_url:
            user_info = token.get("userinfo", {})
        else:
            access_token = token.get("access_token")
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
                response.raise_for_status()
                user_info = response.json()

        email = user_info.get("email")
        if not email:
            return error_redirect("missing_email")

        existing_user = await get_user_by_email(session=session, email=email)
        is_new_user = existing_user is None
        if is_new_user:
            existing_user = await create_social_user(session, email, user_info, provider)

        clear_oauth_session(request)
        return await complete_oauth_login(session, existing_user.email, provider, is_new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{provider} auth callback failed: {e}", exc_info=True)
        return error_redirect(str(e))
