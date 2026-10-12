# LLM Provider Service
**Version:** 2.0.0  
**Last Updated:** 2026-08-03
---
## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Models](#database-models)
4. [Credential Resolution](#credential-resolution)
5. [Provider Chain](#provider-chain)
6. [Provider Catalog](#provider-catalog)
7. [Resilience Layer](#resilience-layer)
8. [Fallback Chain](#fallback-chain)
9. [API Endpoints](#api-endpoints)
10. [Configuration](#configuration)
11. [Default Providers](#default-providers)
12. [Events](#events)
13. [Usage Examples](#usage-examples)
14. [Adding Custom Providers](#adding-custom-providers)
---
## Overview
The LLM Provider Service gives SwX-Core a database-driven way to call large language models through one service layer. It exists so applications can route requests across multiple providers, fall back when one fails, track usage cost and latency, and apply resilience controls without hardcoding one SDK into feature code.
- **Database-driven provider configs** live in `swx_llm_provider_config`, with credentials stored as placeholders
- **Provider chain routing** tries a primary provider first, then lower priority fallbacks
- **Usage logging and resilience** cover tokens, latency, cost, circuit breakers, retries, and timeouts
---
## Architecture
```text
Request -> LLMService -> ProviderFactory -> ProviderChain -> LLM Response

DB Config -> ProviderFactory -> resolve_config(${ENV_VAR}) -> Provider Instance

Provider Call -> CircuitBreaker -> retry_with_backoff -> call_with_timeout
```
---
## Database Models
### `swx_llm_provider_config`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `provider` | string | Provider type such as `openai`, `azure`, `ollama`, or `anthropic` |
| `name` | string | Human readable provider label |
| `model_name` | string | Provider model identifier |
| `credentials` | JSONB | Credential placeholders like `${OPENAI_API_KEY}` |
| `default_params` | JSONB | Default request values such as `temperature`, `max_tokens`, `top_p` |
| `priority` | int | Lower values are preferred earlier in fallback order |
| `is_primary` | bool | Marks the first provider for a supported phase |
| `is_active` | bool | Enables or disables the config |
| `supported_phases` | JSONB | List of phases such as `chat`, `triage`, or `analysis` |
| `cost_per_1k_tokens` | float, nullable | Cost basis used for usage logging |
| `supports_streaming` | bool | Provider can be used by `stream()` |
| `supports_json_mode` | bool | Provider supports JSON response mode |
| `metadata` | JSONB | Extra provider metadata stored via `extra_data` |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
### `swx_llm_usage_log`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `provider_config_id` | UUID, nullable | Linked provider config |
| `provider` | string | Provider used for the request |
| `model_name` | string | Model used for the request |
| `phase` | string, nullable | Requested LLM phase |
| `prompt_tokens` | int | Prompt token count |
| `completion_tokens` | int | Completion token count |
| `total_tokens` | int | Total token count |
| `cost_usd` | float | Computed request cost |
| `latency_ms` | int | End to end latency |
| `success` | bool | Whether the request succeeded |
| `error_message` | string, nullable | Captured error when a call fails |
| `account_id` | UUID, nullable | User or account associated with the request |
| `created_at` | datetime | Creation timestamp |
### `LLMProviderType`
`swx_core/models/llm_provider_config.py` defines four provider enum values: `openai`, `azure`, `ollama`, and `anthropic`.
---
## Credential Resolution
Credential resolution lives in `swx_core/services/llm/config_resolver.py`.
- **`${VAR}`**: required value, raises `ValueError("Required environment variable 'VAR' is not set")` if missing
- **`${VAR:-default}`**: optional value, uses the provided default when the environment variable is absent
- **Nested dicts and string lists** are resolved recursively by `resolve_config()`
- **Secrets are never stored in the database**. Only placeholders are stored in `credentials`
---
## Provider Chain
Provider selection is built in `swx_core/services/llm/provider_factory.py` and `swx_core/repositories/llm_provider_repository.py`.
- `get_primary_for_phase()` returns the active config where `is_primary=True` and the phase is supported, then `get_fallbacks_for_phase()` adds the rest in priority order
- `create_provider()` resolves credentials, builds provider SDK clients, caches instances, and skips configs that cannot be created
The result is an ordered list of `(provider_instance, config)` tuples used by `generate()` and `stream()`.
---
## Resilience Layer
### Circuit breaker
```text
CLOSED -> OPEN -> HALF_OPEN -> CLOSED
```
- `CLOSED`: requests flow normally
- `OPEN`: requests are blocked until the recovery timeout passes
- `HALF_OPEN`: one recovery window opens, success closes the circuit, failure reopens it
`llm_service.generate()` gets a breaker per config using the key `{provider}:{config.id}`.
### Retries and timeout
- `retry_with_backoff()` retries up to `LLM_MAX_RETRIES`, using exponential backoff with jitter
- `call_with_timeout()` wraps provider calls with `asyncio.wait_for()` and raises `LLMTimeoutError` on timeout
- `stream()` uses the circuit breaker, but not the retry or timeout helpers
---
## Provider Catalog

The **Provider Catalog** (`swx_core/services/llm/provider_catalog.py`) resolves the list of available LLM providers from a three-tier cache:

1. **L1 — Redis cache** (1-hour TTL, key `llm:provider_catalog`)
2. **L2 — SystemConfig DB** (key `llm.provider_catalog` under `GENERAL` category)
3. **L3 — Static defaults** (`LLM_PROVIDER_DEFAULTS`)

### Usage

```python
from swx_core.services.llm.provider_catalog import get_provider_catalog, invalidate_catalog_cache

# Read the catalog (auto-caches for 1 hour)
catalog = await get_provider_catalog(session)
# Returns: list[dict] with provider configs

# Invalidate after admin updates the catalog
await invalidate_catalog_cache()
```

### Database-Driven Catalog

Store a custom catalog as JSON in `SystemConfig`:

```sql
INSERT INTO swx_system_config (category, key, value, is_active)
VALUES ('GENERAL', 'llm.provider_catalog', '[
  {"provider": "openai", "model_name": "gpt-4o", "priority": 10},
  {"provider": "anthropic", "model_name": "claude-3-5-sonnet-latest", "priority": 20}
]', true);
```

The catalog is read at startup and cached for 1 hour. Call `invalidate_catalog_cache()` after admin changes.
---
## Fallback Chain

The **Fallback Chain** (`swx_core/services/llm/fallback_service.py`) tries LLM providers in priority order, falling back to the next provider on failure. It integrates with the `CircuitBreakerRegistry` to skip providers with open circuits.

### Error Classification

| Error Type | Behavior |
|---|---|
| `CircuitOpenError` | Skip provider, try next |
| `LLMTimeoutError` | Record circuit failure, try next |
| 4xx client error | Stop chain immediately (bad request) |
| 5xx / other server error | Record circuit failure, try next |
| All providers exhausted | Return `FallbackResult(success=False)` |

### FallbackResult

```python
@dataclass
class FallbackResult:
    success: bool                    # Whether a provider succeeded
    response: LLMResponse | None     # The response (if success)
    stream: AsyncGenerator | None    # Stream handle (if streaming)
    provider_used: str | None        # Provider name that succeeded
    model_used: str | None           # Model name that succeeded
    attempts: list[dict]             # Log of every attempt
    error: str | None                # Final error message
```

### Usage

```python
from swx_core.services.llm.fallback_service import FallbackChain
from swx_core.contracts.llm import LLMRequest

chain = FallbackChain(max_attempts=5)

# Generate with automatic fallback
result = await chain.generate(session, LLMRequest(prompt="Hello"), phase="chat")
if result.success:
    print(f"Used {result.provider_used}/{result.model_used}")

# Stream with automatic fallback
async for event in chain.stream(session, LLMRequest(prompt="Hello"), phase="chat"):
    if event.event_type == "text_delta":
        print(event.data, end="")
```

See [Fallback Chain](FALLBACK_CHAIN.md) for full documentation.
---
## API Endpoints
### Admin Endpoints
All admin routes require `get_current_admin_user` and live under `/admin/llm`.
| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/llm/providers` | Create a provider config |
| `GET` | `/admin/llm/providers` | List provider configs, optional `active_only` query param |
| `GET` | `/admin/llm/providers/{config_id}` | Get one provider config |
| `PUT` | `/admin/llm/providers/{config_id}` | Update a provider config |
| `DELETE` | `/admin/llm/providers/{config_id}` | Delete a provider config |
| `POST` | `/admin/llm/generate` | Test generation with prompt, phase, options, and optional `account_id` |
| `GET` | `/admin/llm/health` | Run `health_check()` across all configured providers |
| `GET` | `/admin/llm/usage/{account_id}` | Get usage summary and logs for an account |
### User Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/user/llm/generate` | Generate as the authenticated user, logs usage with `account_id=current_user.id` |
| `GET` | `/user/llm/usage` | Get the authenticated user's usage summary and logs |
---
## Configuration
LLM settings live in `swx_core/config/settings.py`.
```python
LLM_ENABLED: bool = Field(default=True)
LLM_DEFAULT_TIMEOUT: int = Field(default=60)
LLM_CIRCUIT_BREAKER_THRESHOLD: int = Field(default=5)
LLM_CIRCUIT_BREAKER_RESET_SECONDS: int = Field(default=30)
LLM_MAX_RETRIES: int = Field(default=3)
LLM_USAGE_LOG_ENABLED: bool = Field(default=True)
```
- **`LLM_ENABLED`**: global feature switch for database-driven provider routing
- **`LLM_DEFAULT_TIMEOUT`**: per request timeout in seconds
- **`LLM_CIRCUIT_BREAKER_THRESHOLD`**: failures before a circuit opens
- **`LLM_CIRCUIT_BREAKER_RESET_SECONDS`**: cooldown before a circuit can half-open
- **`LLM_MAX_RETRIES`**: retry count for resilient generate calls
- **`LLM_USAGE_LOG_ENABLED`**: persists cost, latency, and token logs when enabled
---
## Default Providers
`LLM_PROVIDER_DEFAULTS` defines four starter configs.
| Provider | Model | Priority | Env vars | Active | Primary |
|---|---|---:|---|---|---|
| OpenAI | `gpt-4o` | 10 | `OPENAI_API_KEY`, `OPENAI_ORGANIZATION` | Yes | Yes |
| Azure OpenAI | `gpt-4o` | 20 | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` | No | No |
| Anthropic | `claude-3-5-sonnet-latest` | 30 | `ANTHROPIC_API_KEY` | No | No |
| Ollama Local | `llama3.2` | 100 | `OLLAMA_HOST` | Yes | No |
---
## Events
The service dispatches events through `swx_core.events.event_bus`.
| Event name | Payload | When emitted |
|---|---|---|
| `llm.generate` | `{"provider": config.provider, "model": config.model_name, "phase": phase, "account_id": str(account_id) or None}` | After a successful `generate()` call |
---
## Usage Examples
### Calling the service from application code
```python
from swx_core.services.llm import llm_service

result = await llm_service.generate(
    session=session,
    prompt="Summarize this support ticket",
    phase="analysis",
    system_prompt="Return JSON with summary and severity.",
    json_mode=True,
    account_id=current_user.id,
    temperature=0.2,
    max_tokens=512,
)
```
### Creating a provider via admin API
```bash
curl -X POST http://localhost:8001/admin/llm/providers \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "name": "OpenAI GPT-4o Mini",
    "model_name": "gpt-4o-mini",
    "credentials": {"api_key": "${OPENAI_API_KEY}"},
    "default_params": {"temperature": 0.2, "max_tokens": 1024, "top_p": 1.0},
    "priority": 15,
    "is_primary": false,
    "is_active": true,
    "supported_phases": ["chat"],
    "cost_per_1k_tokens": 0.005,
    "supports_streaming": true,
    "supports_json_mode": true,
    "metadata": {"owner": "platform"}
  }'
```
---
## Adding Custom Providers
1. Create a class that extends `BaseLLMProvider` from `swx_core/services/llm/providers/__init__.py`
2. Implement `generate(request: LLMRequest)`, `stream(request: LLMRequest)`, and `health_check()`
3. Accept a `provider_config` dict in the constructor so `model_name` and default params can be passed through
4. Import the class in `swx_core/services/llm/provider_factory.py`
5. Add a new branch in `create_provider()` that maps the stored `provider` value to your implementation
The factory is the registration point. If `create_provider()` does not know your provider type, it will never enter the provider chain.
---
**Status:** LLM provider service documented, ready for use.
