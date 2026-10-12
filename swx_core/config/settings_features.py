# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""
Feature Toggles & Framework Configuration Settings Mixin.

Defines feature toggles and framework configuration: billing, consent,
ledger, LLM, organization, AI, conversation, safety, SSO, status page,
data transfer, feature flags, quotas, usage metering, monitoring, jobs,
and notifications.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class FeaturesSettingsMixin(BaseSettings):
    """Feature toggle and framework configuration."""

    BILLING_ENABLED: bool = Field(
        default=False, description="Enable Stripe billing integration"
    )
    CONSENT_ENABLED: bool = Field(
        default=True, description="Enable consent management framework"
    )
    CONSENT_AUTO_EXPIRE_DAYS: int = Field(
        default=0, description="Auto-expire consents after N days (0 = disabled)"
    )
    LEDGER_ENABLED: bool = Field(
        default=True, description="Enable append-only ledger framework"
    )
    LEDGER_BALANCE_CACHE_TTL: int = Field(
        default=300, description="TTL in seconds for ledger balance cache"
    )
    LEDGER_ALLOW_NEGATIVE_BALANCE: bool = Field(
        default=False, description="Allow balances to go negative"
    )
    LLM_ENABLED: bool = Field(
        default=True, description="Enable database-driven LLM provider routing"
    )
    LLM_DEFAULT_TIMEOUT: int = Field(
        default=60, description="Default timeout in seconds for provider calls"
    )
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = Field(
        default=5, description="Failures before opening an LLM provider circuit"
    )
    LLM_CIRCUIT_BREAKER_RESET_SECONDS: int = Field(
        default=30, description="Seconds before a provider circuit can half-open"
    )
    LLM_MAX_RETRIES: int = Field(
        default=3, description="Maximum retries for resilient provider calls"
    )
    LLM_USAGE_LOG_ENABLED: bool = Field(
        default=True, description="Persist LLM usage logs for cost and latency tracking"
    )
    LLM_STRUCTURED_SSE: bool = Field(
        default=True,
        description="Yield SSEEvent objects from stream() instead of raw strings. Gate for backward compatibility.",
    )
    LLM_DEFAULT_MODELS_OPENAI: list[str] = Field(
        default=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview", "o1-mini"],
        description="Fallback model list for OpenAI when API listing unavailable",
    )
    LLM_DEFAULT_MODELS_AZURE: list[str] = Field(
        default=["gpt-4o", "gpt-4o-mini"],
        description="Fallback model list for Azure OpenAI when API listing unavailable",
    )
    LLM_DEFAULT_MODELS_ANTHROPIC: list[str] = Field(
        default=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
        description="Fallback model list for Anthropic (no model listing API)",
    )
    LLM_DEFAULT_MODELS_OLLAMA: list[str] = Field(
        default=["llama3.2", "mistral", "codellama"],
        description="Fallback model list for Ollama when API listing unavailable",
    )
    SWX_SERVICE_TOKEN: str | None = Field(
        default=None,
        description="Shared secret for service-to-service auth via X-Service-Token header",
        validation_alias=AliasChoices("SWX_SERVICE_TOKEN", "SERVICE_TOKEN", "GATEWAY_SERVICE_TOKEN"),
    )
    SWX_SERVICE_TOKEN_SCOPES: str | None = Field(
        default=None,
        description="Comma-separated permission scopes granted to service principals",
    )
    SWX_AUDIT_RETENTION_DAYS: int | None = Field(
        default=None,
        description="Days to retain audit logs before batch deletion. None or 0 disables retention.",
    )
    SESSION_RETENTION_DAYS: int = Field(
        default=30,
        description="Days to retain refresh tokens before purging expired sessions.",
    )
    SWX_REGIONS: str | None = Field(
        default=None,
        description="JSON mapping of region name → list of country codes for region routing. "
        'Example: \'{"eu": ["DE","FR","NL"], "us": ["US","CA","MX"]}\'',
    )
    SWX_REGION_HEADER: str = Field(
        default="CF-IPCountry",
        description="HTTP header carrying the country code for region routing",
    )
    SWX_AUTH_RATE_LIMIT_RULES: str | None = Field(
        default=None,
        description="JSON array of rate-limit rules for auth endpoints. "
        'Each rule: {"namespace","path_prefix"|"exact_path","methods","max_requests","window_seconds"}',
    )
    ORGANIZATION_ENABLED: bool = Field(
        default=True, description="Enable organization management framework"
    )
    ORGANIZATION_MAX_MEMBERS: int = Field(
        default=0, description="Maximum members allowed per organization (0 = unlimited)"
    )
    ORGANIZATION_INVITATION_EXPIRY_DAYS: int = Field(
        default=7, description="Days before organization invitations expire"
    )
    AUTO_ASSIGN_DEFAULT_ROLE: bool = Field(
        default=True,
        description="Automatically assign DEFAULT_USER_ROLE to new users on registration",
    )
    DEFAULT_USER_ROLE: str = Field(
        default="user",
        description="Role name assigned to newly registered users (requires AUTO_ASSIGN_DEFAULT_ROLE=True)",
    )
    DEFAULT_PLAN_KEY: str = Field(
        default="free",
        description="Plan key for new user billing subscriptions (requires BILLING_ENABLED=True)",
    )
    TRIAL_DAYS: int = Field(
        default=30,
        description="Trial duration in days for new accounts (0 disables trial)",
    )
    TRIAL_PLAN_KEY: str = Field(
        default="enterprise",
        description="Plan key whose entitlements are applied during the trial period",
    )
    AUTO_CREATE_BILLING_ACCOUNT: bool = Field(
        default=True,
        description="Automatically create a billing account for new users on registration",
    )
    AUTO_CREATE_PERSONAL_TEAM: bool = Field(
        default=True,
        description="Automatically create a personal team and set tenant_id for new users on registration",
    )
    STRIPE_API_KEY: str | None = Field(default=None, description="Stripe API key")
    STRIPE_WEBHOOK_SECRET: str | None = Field(
        default=None, description="Stripe webhook secret"
    )
    WEBHOOK_ENABLED: bool = Field(default=True, description="Enable outbound webhooks")
    WEBHOOK_DEFAULT_RETRY_COUNT: int = Field(default=3, description="Default outbound webhook retry count")
    WEBHOOK_DEFAULT_RETRY_DELAY: int = Field(default=60, description="Default outbound webhook retry delay seconds")
    WEBHOOK_DEFAULT_TIMEOUT: int = Field(default=30, description="Default outbound webhook timeout seconds")
    WEBHOOK_MAX_RETRIES: int = Field(default=5, description="Maximum outbound webhook retries")
    WEBHOOK_CIRCUIT_BREAKER_THRESHOLD: int = Field(default=5, description="Outbound webhook circuit breaker threshold")
    LOCAL_CURRENCY_ENABLED: bool = True
    PAYSTACK_SECRET_KEY: str = "${PAYSTACK_SECRET_KEY}"
    PAYSTACK_PUBLIC_KEY: str = "${PAYSTACK_PUBLIC_KEY}"
    PAYSTACK_WEBHOOK_SECRET: str = "${PAYSTACK_WEBHOOK_SECRET}"
    FLUTTERWAVE_SECRET_KEY: str = "${FLUTTERWAVE_SECRET_KEY}"
    FLUTTERWAVE_PUBLIC_KEY: str = "${FLUTTERWAVE_PUBLIC_KEY}"
    FLUTTERWAVE_ENCRYPTION_KEY: str = "${FLUTTERWAVE_ENCRYPTION_KEY}"
    FLUTTERWAVE_WEBHOOK_SECRET: str = "${FLUTTERWAVE_WEBHOOK_SECRET}"
    MPESA_CONSUMER_KEY: str = "${MPESA_CONSUMER_KEY}"
    MPESA_CONSUMER_SECRET: str = "${MPESA_CONSUMER_SECRET}"
    MPESA_PASSKEY: str = "${MPESA_PASSKEY}"
    MPESA_SHORTCODE: str = "${MPESA_SHORTCODE}"
    MPESA_ENV: str = "sandbox"
    EXCHANGE_RATE_SYNC_INTERVAL_HOURS: int = 6
    DEFAULT_TAX_JURISDICTION: str = "NG"
    DEFAULT_BASE_CURRENCY: str = "USD"

    QUOTA_WINDOW_HOURS: int = Field(default=5, description="Rolling usage window size in hours")
    QUOTA_WINDOW_DEFAULT_TOKENS: int = Field(default=100_000, description="Default token quota per window")
    QUOTA_MONTHLY_DEFAULT_TOKENS: int = Field(default=1_000_000, description="Default monthly token quota")
    QUOTA_WINDOW_MAX_RESETS: int = Field(default=1, description="Max window resets per window")
    QUOTA_DAILY_MAX_RESETS: int = Field(default=3, description="Max window resets per day")

    USAGE_METERING_DEFAULT_CURRENCY: str = Field(
        default="NGN", description="Default currency for usage metering wallet debits"
    )
    USAGE_METERING_DEFAULT_MODEL_KEY: str = Field(
        default="default", description="Fallback model key when model is not in pricing table"
    )
    USAGE_METERING_MODEL_PRICING: dict = Field(
        default_factory=lambda: {
            "gpt-4": {"input": 30_000, "output": 60_000},
            "gpt-4o": {"input": 2_500, "output": 10_000},
            "gpt-3.5-turbo": {"input": 500, "output": 1_500},
            "claude-3-opus": {"input": 15_000, "output": 75_000},
            "claude-3-sonnet": {"input": 3_000, "output": 15_000},
            "claude-3-haiku": {"input": 250, "output": 1_250},
            "default": {"input": 1_000, "output": 3_000},
        },
        description="Per-model nano pricing for usage metering (input/output per token)",
    )

    QUOTA_MONTHLY_TTL_DAYS: int = Field(default=32, description="TTL in days for monthly quota Redis keys")
    QUOTA_DAILY_TTL_HOURS: int = Field(default=36, description="TTL in hours for daily reset counter Redis keys")
    QUOTA_WINDOW_TTL_BUFFER_HOURS: int = Field(default=1, description="Extra hours added to window key TTL as buffer")
    WEBHOOK_IDEMPOTENCY_TTL: int = Field(default=604800, description="TTL in seconds for webhook idempotency Redis keys (default: 7 days)")
    WEBHOOK_RETENTION_DAYS: int = Field(default=30, description="Days to retain inbound webhook delivery records")

    SWX_AUDIT_RETENTION_POLICIES: dict = Field(
        default_factory=lambda: {
            "auth": 90,
            "billing": 365,
            "admin": 180,
            "gateway": 30,
            "pii": 2555,
            "usage": 90,
        },
        description="Per-log-type retention days (hot DB retention).",
    )

    MONITORING_ENABLED: bool = Field(
        default=False, description="Enable Sentry monitoring"
    )
    SENTRY_DSN: str | None = Field(
        default=None, description="Sentry DSN for error tracking"
    )

    JOBS_ENABLED: bool = Field(
        default=False, description="Enable Celery background jobs"
    )
    NOTIFICATION_TEMPLATE_DIR: str = Field(default="templates", description="Directory containing file-based notification templates")
    NOTIFICATION_CELERY_TASK_PATH: str = Field(default="swx_core.services.notifications.tasks.send_notification_task", description="Celery task path for queued notification delivery")
    NOTIFICATION_BRAND_COLOR: str = Field(default="#3c42b6", description="Default brand color for notification templates")
    NOTIFICATION_SUPPORT_EMAIL: str = Field(default="support@example.com", description="Support email injected into notification templates")
    AI_ENABLED: bool = Field(
        default=False, description="Enable AI/vector embeddings (pgai)"
    )

    CONVERSATION_ENABLED: bool = Field(default=True, description="Enable conversation state tracking")
    CONVERSATION_DEFAULT_PAGE_SIZE: int = Field(default=50, description="Default page size for conversation listing")
    CONVERSATION_MAX_MESSAGE_LENGTH: int = Field(default=10000, description="Maximum message content length in characters")
    CONVERSATION_CACHE_TTL: int = Field(default=30, description="Conversation config cache TTL in seconds")

    # AI Safety & Content Filtering
    SAFETY_ENABLED: bool = Field(default=True, description="Enable AI safety and content filtering")
    SAFETY_DEFAULT_ACTION: str = Field(default="flag", description="Default action when content is flagged (allow, flag, block, replace)")
    SAFETY_CACHE_TTL: int = Field(default=60, description="Safety filter config cache TTL in seconds")
    SAFETY_MAX_CONTENT_LENGTH: int = Field(default=50000, description="Maximum content length for safety checks in characters")
    SAFETY_LOG_ALL_CHECKS: bool = Field(default=True, description="Log all safety checks for audit trail")

    # Enterprise SSO
    SSO_ENABLED: bool = Field(default=True, description="Enable enterprise SSO (SAML/OIDC)")
    SSO_CACHE_TTL: int = Field(default=60, description="SSO provider config cache TTL in seconds")
    SSO_SESSION_TIMEOUT: int = Field(default=28800, description="SSO session timeout in seconds (default 8 hours)")
    SSO_ALLOW_MULTIPLE_SESSIONS: bool = Field(default=True, description="Allow users to have multiple active SSO sessions")

    # Status Page
    STATUS_ENABLED: bool = Field(default=True, description="Enable status page and incident tracking")
    STATUS_CACHE_TTL: int = Field(default=30, description="Status page cache TTL in seconds")
    STATUS_DEFAULT_PAGE_SIZE: int = Field(default=50, description="Default page size for status listings")

    # Data Export/Import
    DATA_TRANSFER_ENABLED: bool = Field(default=True, description="Enable data export and import")
    DATA_TRANSFER_CACHE_TTL: int = Field(default=60, description="Data transfer config cache TTL in seconds")
    DATA_EXPORT_EXPIRY_DAYS: int = Field(default=7, description="Number of days before export files expire")
    DATA_EXPORT_MAX_RECORDS: int = Field(default=100000, description="Maximum records per export")
    DATA_IMPORT_MAX_FILE_SIZE: int = Field(default=52428800, description="Maximum import file size in bytes (50MB)")

    @property
    def is_billing_available(self) -> bool:
        if not self.BILLING_ENABLED:
            return False
        try:
            import stripe

            return stripe is not None
        except ImportError:
            return False

    @property
    def is_monitoring_available(self) -> bool:
        """Check if monitoring is available (enabled + sentry installed)."""
        if not self.MONITORING_ENABLED:
            return False
        try:
            import sentry_sdk

            return sentry_sdk is not None
        except ImportError:
            return False

    @property
    def is_jobs_available(self) -> bool:
        """Check if jobs is available (enabled + celery installed)."""
        if not self.JOBS_ENABLED:
            return False
        try:
            import celery  # pyright: ignore[reportMissingTypeStubs]

            return celery is not None
        except ImportError:
            return False

    @property
    def is_ai_available(self) -> bool:
        """Check if AI is available (enabled + pgai installed)."""
        if not self.AI_ENABLED:
            return False
        try:
            import pgai

            return pgai is not None
        except ImportError:
            return False
