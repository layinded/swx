"""
OAuth Provider Registry
-----------------------
Extensible registry for custom social auth providers.

Allows adding new providers (GitHub, LinkedIn, Apple, etc.) via configuration
without modifying core code.

Usage:
    # In settings.py or .env:
    OAUTH_PROVIDERS = "github,linkedin"

    # GitHub provider config:
    GITHUB_CLIENT_ID = "xxx"
    GITHUB_CLIENT_SECRET = "xxx"
    GITHUB_REDIRECT_URI = "http://localhost:8001/api/oauth/github/callback"

    # Custom provider:
    CUSTOM_PROVIDER_AUTH_URL = "https://provider.com/oauth/authorize"
    CUSTOM_PROVIDER_TOKEN_URL = "https://provider.com/oauth/token"
    CUSTOM_PROVIDER_USER_INFO_URL = "https://api.provider.com/user"
"""

from typing import Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OAuthProviderConfig:
    def __init__(
        self,
        name: str,
        client_id: str | None,
        client_secret: str | None,
        redirect_uri: str | None,
        redirect_uris: list[str] | None = None,
        auth_url: str | None = None,
        token_url: str | None = None,
        user_info_url: str | None = None,
        scope: str | None = None,
        server_metadata_url: str | None = None,
    ):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.redirect_uris = redirect_uris or []
        self.auth_url = auth_url
        self.token_url = token_url
        self.user_info_url = user_info_url
        self.scope = scope
        self.server_metadata_url = server_metadata_url

    def to_oauth_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        if self.server_metadata_url:
            config["server_metadata_url"] = self.server_metadata_url
        else:
            if self.auth_url:
                config["authorize_url"] = self.auth_url
            if self.token_url:
                config["access_token_url"] = self.token_url

        if self.scope:
            config["client_kwargs"] = {"scope": self.scope}

        return config


class OAuthProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="allow",
    )

    OAUTH_PROVIDERS: str = Field(
        default="",
        description="Comma-separated list of enabled OAuth providers (e.g., 'github,linkedin,apple')",
    )

    def get_provider_configs(self) -> dict[str, OAuthProviderConfig]:
        providers = {}
        enabled_providers = [p.strip() for p in self.OAUTH_PROVIDERS.split(",") if p.strip()]

        for provider in enabled_providers:
            provider_upper = provider.upper()

            client_id = getattr(self, f"{provider_upper}_CLIENT_ID", None)
            client_secret = getattr(self, f"{provider_upper}_CLIENT_SECRET", None)
            redirect_uri = getattr(self, f"{provider_upper}_REDIRECT_URI", None)
            redirect_uris_raw = getattr(self, f"{provider_upper}_REDIRECT_URIS", None)

            # Parse comma-separated redirect URIs from env
            redirect_uris: list[str] = []
            if isinstance(redirect_uris_raw, str):
                redirect_uris = [u.strip() for u in redirect_uris_raw.split(",") if u.strip()]
            elif isinstance(redirect_uris_raw, list):
                redirect_uris = redirect_uris_raw

            if not all([client_id, client_secret, redirect_uri]):
                continue

            config = OAuthProviderConfig(
                name=provider,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                redirect_uris=redirect_uris,
                auth_url=getattr(self, f"{provider_upper}_AUTH_URL", None),
                token_url=getattr(self, f"{provider_upper}_TOKEN_URL", None),
                user_info_url=getattr(self, f"{provider_upper}_USER_INFO_URL", None),
                scope=getattr(self, f"{provider_upper}_SCOPE", None),
                server_metadata_url=getattr(self, f"{provider_upper}_SERVER_METADATA_URL", None),
            )
            providers[provider] = config

        return providers


oauth_provider_settings = OAuthProviderSettings()