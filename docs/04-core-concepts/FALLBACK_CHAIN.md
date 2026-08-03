# Fallback Chain Service

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [FallbackResult](#fallbackresult)
4. [Usage Examples](#usage-examples)
5. [Configuration](#configuration)
6. [Error Handling](#error-handling)

---

## Overview

The **Fallback Chain** service tries LLM providers in priority order, falling back to the next provider when the current one fails. It integrates with the existing `CircuitBreaker` from the resilience layer so that permanently-broken providers are automatically skipped.

Key features:

- **Priority-based fallback** — tries providers in database order (lower `priority` first)
- **Circuit breaker integration** — skips providers with open circuits
- **Client error stop** — stops immediately on 4xx errors (the request is bad, not the provider)
- **Server error retry** — retries on 5xx, timeouts, and `CircuitOpenError`
- **Structured attempts log** — every attempt is recorded with provider, model, and error

Module: `swx_core/services/llm/fallback_service.py`

---

## How It Works

```
Request → FallbackChain.generate(session, request, phase="chat")
  │
  ├─ Provider 1 (primary) → Success → Return FallbackResult(success=True)
  │                      → 5xx/timeout → Record failure, try next
  │                      → 4xx → Stop immediately, return FallbackResult(success=False)
  │                      → Circuit open → Skip, try next
  │
  ├─ Provider 2 (fallback) → ...
  │
  └─ All providers failed → Return FallbackResult(success=False, error="...")
```

### Error Classification

| Error Type | Behavior |
|---|---|
| `CircuitOpenError` | Skip provider, try next |
| `LLMTimeoutError` | Record circuit failure, try next |
| 4xx client error | Stop chain immediately (bad request) |
| 5xx / other server error | Record circuit failure, try next |
| All providers exhausted | Return `FallbackResult(success=False)` |

---

## FallbackResult

```python
@dataclass
class FallbackResult:
    success: bool                          # Whether a provider succeeded
    response: LLMResponse | None          # The response (if success)
    stream: AsyncGenerator | None         # Stream handle (if streaming)
    provider_used: str | None              # Provider name that succeeded
    model_used: str | None                 # Model name that succeeded
    attempts: list[dict]                  # Log of every attempt
    error: str | None                     # Final error message
```

---

## Usage Examples

### Generate with Fallback

```python
from swx_core.services.llm.fallback_service import FallbackChain
from swx_core.contracts.llm import LLMRequest

chain = FallbackChain(max_attempts=5)
result = await chain.generate(session, LLMRequest(prompt="Hello"), phase="chat")

if result.success:
    print(f"Used {result.provider_used}/{result.model_used}")
    print(f"Response: {result.response.content}")
else:
    print(f"All providers failed: {result.error}")
```

### Stream with Fallback

```python
async for event in chain.stream(session, LLMRequest(prompt="Hello"), phase="chat"):
    if event.event_type == "text_delta":
        print(event.data, end="")
    elif event.event_type == "usage":
        print(f"\nTokens: {event.data}")
    elif event.event_type == "error":
        print(f"\nStream error: {event.data}")
```

### Inspecting Attempts

```python
result = await chain.generate(session, request, phase="chat")
for attempt in result.attempts:
    print(f"  {attempt['provider']}/{attempt['model']}: "
          f"{'OK' if attempt.get('success') else attempt.get('error', 'unknown')}")
```

---

## Configuration

The fallback chain uses the existing `CircuitBreakerRegistry` and `get_provider_chain()` from the LLM service. No additional configuration is required.

| Setting | Default | Description |
|---|---|---|
| `LLM_CIRCUIT_BREAKER_THRESHOLD` | 5 | Failures before opening circuit |
| `LLM_CIRCUIT_BREAKER_RESET_SECONDS` | 30 | Seconds before half-open |
| `LLM_MAX_RETRIES` | 3 | Max retries for resilient calls |
| `max_attempts` (constructor) | 5 | Max providers to try in chain |

---

## Error Handling

The chain raises `RuntimeError` from `stream()` only when all providers fail. For `generate()`, errors are captured in the `FallbackResult.error` field. Client errors (4xx) stop the chain immediately since the request itself is invalid.