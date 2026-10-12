# SwX v2.0.0 Documentation Index

Framework-grade documentation for production deployment.

---

## 00. Release

- [RELEASE_CHECKLIST.md](00-release/RELEASE_CHECKLIST.md) - Pre-release validation checklist

## 01. Overview

- [OVERVIEW.md](01-overview/OVERVIEW.md) - Framework introduction and architecture
- [FEATURES.md](01-overview/FEATURES.md) - Complete feature list
- [DEPENDENCIES.md](01-overview/DEPENDENCIES.md) - Optional dependencies guide (v2.3.0+)

## 02. Getting Started

- [GETTING_STARTED.md](02-getting-started/GETTING_STARTED.md) - Installation and setup
- [QUICKSTART.md](02-getting-started/QUICKSTART.md) - 5-minute quickstart guide
- [INSTALLATION.md](02-getting-started/INSTALLATION.md) - Detailed installation options

## 03. Architecture

- [ARCHITECTURE.md](03-architecture/ARCHITECTURE.md) - System architecture
- [DIRECTORY_STRUCTURE.md](03-architecture/DIRECTORY_STRUCTURE.md) - Project layout
- [SERVICE_CONTAINER.md](03-architecture/SERVICE_CONTAINER.md) - Dependency injection container
- [REQUEST_LIFECYCLE.md](03-architecture/REQUEST_LIFECYCLE.md) - Request processing flow

## 04. Core Concepts

- [CACHING.md](04-core-concepts/CACHING.md) - L1/L2 caching: auth, feature flags, roles, settings, CacheService, tenant config cache (v2.11.0)
- [CORE_PATTERNS.md](04-core-concepts/CORE_PATTERNS.md) - Design patterns overview
- [BASE_CLASSES.md](04-core-concepts/BASE_CLASSES.md) - Controller-Service-Repository pattern (v2.0)
- [UTILITIES.md](04-core-concepts/UTILITIES.md) - Utilities reference (v2.0)
- [SERVICE_CONTAINER.md](04-core-concepts/SERVICE_CONTAINER.md) - IoC container usage
- [SERVICE_PROVIDERS.md](04-core-concepts/SERVICE_PROVIDERS.md) - Provider pattern
- [GUARDS.md](04-core-concepts/GUARDS.md) - Authentication guards
- [EVENT_BUS.md](04-core-concepts/EVENT_BUS.md) - Event-driven architecture
- [MIDDLEWARE.md](04-core-concepts/MIDDLEWARE.md) - Request/response middleware
- [RBAC.md](04-core-concepts/RBAC.md) - Role-based access control
- [POLICY_ENGINE.md](04-core-concepts/POLICY_ENGINE.md) - Attribute-based access control
- [TOKEN_REVOCATION.md](04-core-concepts/TOKEN_REVOCATION.md) - Token blacklisting
- [BACKGROUND_JOBS.md](04-core-concepts/BACKGROUND_JOBS.md) - Celery integration
- [PLUGIN_SYSTEM.md](04-core-concepts/PLUGIN_SYSTEM.md) - Extensibility
- [LLM_PROVIDER.md](04-core-concepts/LLM_PROVIDER.md) - LLM provider service, fallback chain, provider catalog (v2.0)
- [RATE_LIMITING.md](04-core-concepts/RATE_LIMITING.md) - Rate limiting and abuse protection (v2.12.0)
- [AUDIT_LOGS.md](04-core-concepts/AUDIT_LOGS.md) - Audit logging, retention, event queue (v2.0)
- [BILLING.md](04-core-concepts/BILLING.md) - Billing and entitlements
- [FALLBACK_CHAIN.md](04-core-concepts/FALLBACK_CHAIN.md) - LLM fallback chain with circuit breaker (NEW)
- [ONBOARDING.md](04-core-concepts/ONBOARDING.md) - User onboarding step tracking (NEW)
- [REGION_ROUTING.md](04-core-concepts/REGION_ROUTING.md) - Region routing middleware (NEW)
- [AUTH_RATE_LIMITING.md](04-core-concepts/AUTH_RATE_LIMITING.md) - Auth rate limiting middleware (NEW)
- [RESILIENCE.md](04-core-concepts/RESILIENCE.md) - LLM circuit breaker, retry, and timeout (NEW)
- [ERROR_HANDLING.md](04-core-concepts/ERROR_HANDLING.md) - Structured error hierarchy and convenience functions (NEW)
- [PROMPT_INJECTION.md](04-core-concepts/PROMPT_INJECTION.md) - Prompt injection detection and scoring (NEW)
- [COMPLIANCE_REPORTS.md](04-core-concepts/COMPLIANCE_REPORTS.md) - Compliance readiness reports (GDPR, HIPAA, CCPA, DORA, FERPA) (NEW)
- [LAZY_IMPORT.md](04-core-concepts/LAZY_IMPORT.md) - Lazy import proxy for circular imports and startup optimization (NEW)

## 05. Security

- [SECURITY_MODEL.md](05-security/SECURITY_MODEL.md) - Security architecture
- [SECURITY_HARDENING.md](05-security/SECURITY_HARDENING.md) - Production hardening
- [TOKEN_SECURITY.md](05-security/TOKEN_SECURITY.md) - JWT security
- [SECRETS_MANAGEMENT.md](05-security/SECRETS_MANAGEMENT.md) - Secret handling
- [AUTHENTICATION.md](05-security/AUTHENTICATION.md) - Auth flows
- [AUTHORIZATION.md](05-security/AUTHORIZATION.md) - Permission system
- [ENCRYPTION.md](05-security/ENCRYPTION.md) - Versioned Fernet encryption with key rotation (NEW)
- [SECURITY_HEADERS.md](05-security/SECURITY_HEADERS.md) - Pure-ASGI security headers middleware (NEW)
- [CSRF_PROTECTION.md](05-security/CSRF_PROTECTION.md) - CSRF middleware with cookie lifecycle (NEW)
- [AUTH_GUARDS.md](05-security/AUTH_GUARDS.md) - JWT, API key, service token, and combined auth guards (NEW)

## 06. API Usage

- [API_USAGE.md](06-api-usage/API_USAGE.md) - General API patterns
- [API_REFERENCE.md](06-api-usage/API_REFERENCE.md) - Complete endpoint reference
- [ERROR_HANDLING.md](06-api-usage/ERROR_HANDLING.md) - Error responses
- [PAGINATION_FILTERING.md](06-api-usage/PAGINATION_FILTERING.md) - Query patterns

## 07. Extending

- [EXTENSION_GUIDE.md](07-extending/EXTENSION_GUIDE.md) - Complete extensibility guide
- [EXTENDING_MODELS.md](07-extending/EXTENDING_MODELS.md) - Model extension patterns (Profile, Mixins, Feature Registry, Base Classes, Service Extension) (NEW)
- [CUSTOM_PROVIDERS.md](07-extending/CUSTOM_PROVIDERS.md) - Service providers
- [CUSTOM_GUARDS.md](07-extending/CUSTOM_GUARDS.md) - Authentication guards
- [CUSTOM_MIDDLEWARE.md](07-extending/CUSTOM_MIDDLEWARE.md) - Middleware
- [CUSTOM_EVENTS.md](07-extending/CUSTOM_EVENTS.md) - Event system
- [PLUGIN_DEVELOPMENT.md](07-extending/PLUGIN_DEVELOPMENT.md) - Plugin development
- [ADDING_FEATURES.md](07-extending/ADDING_FEATURES.md) - Feature development

## 08. Operations

- [DEPLOYMENT.md](08-operations/DEPLOYMENT.md) - Production deployment guide
- [DOCKER_DEPLOYMENT.md](08-operations/DOCKER_DEPLOYMENT.md) - Docker deployment
- [MULTI_NODE.md](08-operations/MULTI_NODE.md) - Multi-node deployment
- [MONITORING.md](08-operations/MONITORING.md) - Observability
- [METRICS.md](08-operations/METRICS.md) - Prometheus metrics
- [LOGGING.md](08-operations/LOGGING.md) - Logging configuration
- [BACKUP_RESTORE.md](08-operations/BACKUP_RESTORE.md) - Data management

## 09. Testing

- [TESTING_GUIDE.md](09-testing/TESTING_GUIDE.md) - Testing strategies
- [UNIT_TESTS.md](09-testing/UNIT_TESTS.md) - Unit testing
- [INTEGRATION_TESTS.md](09-testing/INTEGRATION_TESTS.md) - Integration testing
- [E2E_TESTS.md](09-testing/E2E_TESTS.md) - End-to-end testing
- [ACCEPTANCE_TESTING.md](09-testing/ACCEPTANCE_TESTING.md) - Acceptance criteria

## 10. Troubleshooting

- [TROUBLESHOOTING.md](10-troubleshooting/TROUBLESHOOTING.md) - Common issues
- [FAQ.md](10-troubleshooting/FAQ.md) - Frequently asked questions
- [DEBUGGING.md](10-troubleshooting/DEBUGGING.md) - Debugging techniques
- [ERROR_CODES.md](10-troubleshooting/ERROR_CODES.md) - Error code reference

## 11. Reference

- [CLI_REFERENCE.md](11-reference/CLI_REFERENCE.md) - CLI commands
- [CONFIGURATION.md](11-reference/CONFIGURATION.md) - Configuration options
- [ENVIRONMENT_VARIABLES.md](11-reference/ENVIRONMENT_VARIABLES.md) - Environment config
- [MIGRATION_GUIDE.md](11-reference/MIGRATION_GUIDE.md) - Migration from v1
- [CHANGELOG.md](11-reference/CHANGELOG.md) - Version history
- [GLOSSARY.md](11-reference/GLOSSARY.md) - Terms and definitions

---

## Quick Reference Cards

### CLI Commands

```bash
swx setup              # Initial setup wizard
swx serve              # Development server
swx doctor             # System diagnostics
swx optimize           # Optimize cache
swx route:list         # List routes
swx plugin:list        # List plugins
swx upgrade            # Upgrade framework
```

### Container Usage

```python
from swx_core import Container

# Binding
container.bind("service", MyService)           # Transient
container.singleton("cache", RedisCache)       # Singleton
container.scoped("session", Session)           # Scoped

# Resolution
service = container.make("service")

# Contextual
container.when("BillingService").needs("CacheInterface").give(RedisCache)
```

### Guard Usage

```python
from swx_core.guards import JWTGuard

guard = JWTGuard(
    secret_key="...",
    token_blacklist=redis_blacklist,
    strict_blacklist=True  # Fail-closed
)

user = await guard.authenticate(request)
```

### Event Bus

```python
from swx_core.events import EventBus

@event_bus.listen("user.registered")
async def on_user_registered(event):
    await send_welcome_email(event.payload["user"])
```

---

## Documentation Standards

1. **Code examples must be runnable** - All code blocks are tested
2. **No marketing language** - Technical accuracy only
3. **Include error handling** - Show both happy and unhappy paths
4. **Cross-reference** - Link to related documentation
5. **Version-specific** - Mark version requirements explicitly