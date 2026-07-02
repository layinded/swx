# OAuth Provider Extensibility

**Version:** 2.7.34
**Last Updated:** 2026-07-02

---

## Overview

swx-core supports extensible OAuth authentication with **PKCE** and **Backend-for-Frontend (BFF) pattern** following RFC 9700 security best practices.

### Security Features

| Feature | Standard | Implementation |
|---------|----------|----------------|
| **PKCE** | RFC 7636 | Mandatory, S256 method |
| **CSRF Protection** | OAuth 2.0 | State parameter validation |
| **Token Storage** | OWASP | HTTP-only cookies |
| **Token Delivery** | BFF Pattern | Server-side only |

---

## Built-in Providers

swx-core includes built-in support for:

- **Google** — OpenID Connect with `server_metadata_url`
- **Facebook** — OAuth 2.0 with Graph API

These are configured via `SocialLoginSettings`:

```bash
# .env
ENABLE_SOCIAL_LOGIN=true
ENABLE_GOOGLE_LOGIN=true
ENABLE_FACEBOOK_LOGIN=false

GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8001/api/oauth/google/callback
```

---

## Adding Custom Providers

### Configuration

Add providers via environment variables:

```bash
# .env
OAUTH_PROVIDERS=github,linkedin,apple

# GitHub
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=http://localhost:8001/api/oauth/github/callback
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user
GITHUB_SCOPE=user:email

# LinkedIn
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/oauth/linkedin/callback
LINKEDIN_AUTH_URL=https://www.linkedin.com/oauth/v2/authorization
LINKEDIN_TOKEN_URL=https://www.linkedin.com/oauth/v2/accessToken
LINKEDIN_USER_INFO_URL=https://api.linkedin.com/v2/me
LINKEDIN_SCOPE=r_emailaddress r_liteprofile

# Apple (uses OIDC Discovery)
APPLE_CLIENT_ID=your-apple-client-id
APPLE_CLIENT_SECRET=your-apple-client-secret
APPLE_REDIRECT_URI=http://localhost:8001/api/oauth/apple/callback
APPLE_SERVER_METADATA_URL=https://appleid.apple.com/.well-known/openid-configuration
APPLE_SCOPE=email name
```

### Required Variables

Each custom provider requires:

| Variable | Description |
|----------|-------------|
| `{PROVIDER}_CLIENT_ID` | OAuth client ID |
| `{PROVIDER}_CLIENT_SECRET` | OAuth client secret |
| `{PROVIDER}_REDIRECT_URI` | Callback URL |

### Optional Variables

| Variable | Description |
|----------|-------------|
| `{PROVIDER}_AUTH_URL` | Authorization endpoint |
| `{PROVIDER}_TOKEN_URL` | Token endpoint |
| `{PROVIDER}_USER_INFO_URL` | User info endpoint (for non-OIDC providers) |
| `{PROVIDER}_SCOPE` | OAuth scopes |
| `{PROVIDER}_SERVER_METADATA_URL` | OIDC discovery URL (alternative to auth_url/token_url) |

---

## Provider Types

### OIDC Providers (Recommended)

Use `SERVER_METADATA_URL` for OpenID Connect providers:

```bash
# Google (already built-in, but shown for reference)
GOOGLE_SERVER_METADATA_URL=https://accounts.google.com/.well-known/openid-configuration

# Apple
APPLE_SERVER_METADATA_URL=https://appleid.apple.com/.well-known/openid-configuration

# Keycloak
KEYCLOAK_SERVER_METADATA_URL=https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration
```

OIDC providers return `userinfo` automatically — no `USER_INFO_URL` needed.

### OAuth 2.0 Providers

Use `AUTH_URL`, `TOKEN_URL`, and `USER_INFO_URL` for standard OAuth 2.0:

```bash
# GitHub
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user

# LinkedIn
LINKEDIN_AUTH_URL=https://www.linkedin.com/oauth/v2/authorization
LINKEDIN_TOKEN_URL=https://www.linkedin.com/oauth/v2/accessToken
LINKEDIN_USER_INFO_URL=https://api.linkedin.com/v2/me
```

---

## API Endpoints

### Get OAuth URLs

```http
GET /api/oauth/urls

Response:
{
  "google": "http://localhost:8001/api/oauth/google",
  "facebook": "http://localhost:8001/api/oauth/facebook",
  "github": "http://localhost:8001/api/oauth/github",
  "linkedin": "http://localhost:8001/api/oauth/linkedin"
}
```

### Initiate Login

```http
GET /api/oauth/{provider}

# Examples:
GET /api/oauth/google
GET /api/oauth/github
GET /api/oauth/linkedin
```

Redirects to the provider's authorization page.

### Callback

```http
GET /api/oauth/{provider}/callback?code=...&state=...

# Examples:
GET /api/oauth/google/callback?code=...&state=...
GET /api/oauth/github/callback?code=...&state=...
```

Returns JWT token on success.

---

## Flow

1. **Initiate** — `GET /api/oauth/{provider}` redirects to provider
2. **Authorize** — User approves on provider's site
3. **Callback** — Provider redirects to `/api/oauth/{provider}/callback`
4. **Authenticate** — swx-core exchanges code for token
5. **User Info** — swx-core fetches user email from provider
6. **Login/Register** — User logged in or registered automatically

---

## User Creation and Events

When a new user registers via OAuth, swx-core uses the same registration flow as traditional email/password registration to ensure all lifecycle hooks and events fire:

```python
# swx_core/routes/access/oauth_route.py (Google example)
user_in = UserCreate(
    email=email,
    password=secrets.token_urlsafe(32),  # Random placeholder, unused for social auth
    full_name=user_info.get("name"),
)

user = await register_user_service(
    session=session,
    user_in=user_in,
    request=request,
    auth_provider="google",
    provider_id=user_info.get("sub"),  # Provider-specific ID
    event_context={"social_provider": "google"},
)
```

### Event Emission

This ensures the **`user.created`** event fires, triggering all listeners:

| Listener | What It Does |
|----------|--------------|
| **NotificationListener** | Sends welcome notification |
| **UserCreatedBillingListener** | Creates billing account, user profile, PII policy, onboarding steps |
| **UserCreatedAuditListener** | Logs user creation in audit trail |
| **Custom listeners** | Any app-specific hooks |

### Event Context

The `event_context` parameter passes provider information to listeners:

```python
{
    "social_provider": "google"  # or "facebook", "github", etc.
}
```

### User Model

Created users have these fields set:

```python
User(
    email=email,
    full_name=user_info.get("name"),
    auth_provider="google",      # Provider name
    provider_id="google-sub-id", # Provider's unique ID
    is_active=True,
    is_verified=True,            # OAuth emails are verified
)
```

### What Happens on Registration

1. **pre_register_hook** runs (if configured)
2. **User created** in database with `auth_provider` and `provider_id`
3. **post_register_hook** runs (if configured)
4. **`user.created` event emitted**
5. **All listeners fire**:
   - Billing account created
   - User profile created
   - PII policy initialized
   - Onboarding steps set up
   - Welcome notification sent
   - Email verification sent (if applicable)

---

## Common Provider Configurations

### GitHub

```bash
GITHUB_CLIENT_ID=Iv1.abc123...
GITHUB_CLIENT_SECRET=abc123...
GITHUB_REDIRECT_URI=http://localhost:8001/api/oauth/github/callback
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user
GITHUB_SCOPE=user:email
```

### LinkedIn

```bash
LINKEDIN_CLIENT_ID=78abc123...
LINKEDIN_CLIENT_SECRET=abc123...
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/oauth/linkedin/callback
LINKEDIN_AUTH_URL=https://www.linkedin.com/oauth/v2/authorization
LINKEDIN_TOKEN_URL=https://www.linkedin.com/oauth/v2/accessToken
LINKEDIN_USER_INFO_URL=https://api.linkedin.com/v2/me
LINKEDIN_SCOPE=r_emailaddress r_liteprofile
```

### Apple (OIDC)

```bash
APPLE_CLIENT_ID=com.yourapp.auth
APPLE_CLIENT_SECRET=abc123...
APPLE_REDIRECT_URI=http://localhost:8001/api/oauth/apple/callback
APPLE_SERVER_METADATA_URL=https://appleid.apple.com/.well-known/openid-configuration
APPLE_SCOPE=email name
```

### Microsoft (OIDC)

```bash
MICROSOFT_CLIENT_ID=abc123-456-def...
MICROSOFT_CLIENT_SECRET=abc123...
MICROSOFT_REDIRECT_URI=http://localhost:8001/api/oauth/microsoft/callback
MICROSOFT_SERVER_METADATA_URL=https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration
MICROSOFT_SCOPE=openid email profile
```

### GitLab

```bash
GITLAB_CLIENT_ID=abc123...
GITLAB_CLIENT_SECRET=abc123...
GITLAB_REDIRECT_URI=http://localhost:8001/api/oauth/gitlab/callback
GITLAB_AUTH_URL=https://gitlab.com/oauth/authorize
GITLAB_TOKEN_URL=https://gitlab.com/oauth/token
GITLAB_USER_INFO_URL=https://gitlab.com/api/v4/user
GITLAB_SCOPE=read_user
```

---

## Testing

### Test Callback Flow

```python
import httpx

async def test_oauth_flow():
    async with httpx.AsyncClient() as client:
        # 1. Get OAuth URLs
        response = await client.get("http://localhost:8001/api/oauth/urls")
        urls = response.json()
        assert "github" in urls
        
        # 2. Initiate login
        response = await client.get(urls["github"], follow_redirects=False)
        assert response.status_code == 302
        authorize_url = response.headers["Location"]
        
        # 3. Simulate callback (for testing only)
        # In production, user visits authorize_url and is redirected back
```

---

## Security Considerations

### CSRF Protection

swx-core uses `state` parameter for CSRF protection:

1. Generate random `state` token
2. Store in session: `request.session["oauth_state"] = state`
3. Provider redirects back with `state` parameter
4. Verify: `state == request.session["oauth_state"]`

### PKCE (Optional)

For public clients, implement PKCE:

```python
import secrets
import hashlib
import base64

def generate_pkce_verifier():
    return secrets.token_urlsafe(32)

def generate_pkce_challenge(verifier):
    hashed = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(hashed).decode().rstrip('=')
```

---

## Troubleshooting

### "provider_login_disabled"

The provider is not in `OAUTH_PROVIDERS` or required config is missing.

**Solution:** Check `.env` has:
```bash
OAUTH_PROVIDERS=github
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=xxx
```

### "failed_to_fetch_{provider}_token"

Token exchange failed.

**Solution:** Check:
- Client ID/Secret are correct
- Redirect URI matches exactly
- Provider's API is accessible

### "{provider}_account_missing_email"

User info doesn't contain email.

**Solution:**
- Ensure `SCOPE` includes `email`
- Check provider's API response format
- Some providers require additional permissions

---

## Related Documentation

- [Authentication](AUTHENTICATION.md) - Auth flows and token security
- [Registration Hooks](REGISTRATION_HOOKS.md) - Post-registration customization