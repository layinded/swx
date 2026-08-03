# LLM Resilience

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Circuit Breaker](#circuit-breaker)
3. [Circuit Breaker Registry](#circuit-breaker-registry)
4. [Retry with Backoff](#retry-with-backoff)
5. [Timeout](#timeout)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)

---

## Overview

The **LLM Resilience** module (`swx_core/services/llm/resilience.py`) provides circuit breaker, retry with exponential backoff, and timeout utilities for LLM provider calls. These are used by `llm_service.generate()` and `fallback_service.FallbackChain` to handle transient failures gracefully.

---

## Circuit Breaker

The circuit breaker prevents cascading failures by blocking requests to a failing provider until it recovers.

### State Machine

```
CLOSED → OPEN → HALF_OPEN → CLOSED
           ↑          │
           └──────────┘  (failure in half-open reopens)
```

| State | Behavior |
|---|---|
| **CLOSED** | Requests flow normally |
| **OPEN** | Requests are blocked until recovery timeout passes |
| **HALF_OPEN** | One recovery request is allowed; success closes, failure reopens |

### Construction

```python
from swx_core.services.llm.resilience import CircuitBreaker

breaker = CircuitBreaker(
    name="openai:gpt-4o",
    failure_threshold=5,      # Failures before opening
    success_threshold=1,      # Successes in half-open to close
    recovery_timeout_seconds=30,  # Seconds before half-open
)
```

### Async Methods

| Method | Description |
|---|---|
| `await breaker.allow_request()` | Check if a request should proceed |
| `await breaker.record_success()` | Record a successful call |
| `await breaker.record_failure()` | Record a failed call |

All methods use `asyncio.Lock` for thread-safe state transitions under high concurrency.

---

## Circuit Breaker Registry

The `CircuitBreakerRegistry` manages named circuit breakers as singletons:

```python
from swx_core.services.llm.resilience import CircuitBreakerRegistry

# Get or create a breaker (idempotent)
breaker = CircuitBreakerRegistry.get("openai:gpt-4o", failure_threshold=5)

# Check all states
states = CircuitBreakerRegistry.all_states()
# {"openai:gpt-4o": "closed", "anthropic:claude-3-5-sonnet": "open"}

# Reset a specific breaker
CircuitBreakerRegistry.reset("openai:gpt-4o")

# Reset all breakers
CircuitBreakerRegistry.reset()
```

---

## Retry with Backoff

`retry_with_backoff()` retries an async callable with exponential backoff and jitter:

```python
from swx_core.services.llm.resilience import retry_with_backoff

result = await retry_with_backoff(
    fn=lambda: call_provider(provider, request),
    max_retries=3,
    base_delay=1.0,     # Initial delay in seconds
    max_delay=30.0,     # Maximum delay cap
    circuit_breaker=breaker,  # Optional: check breaker before each attempt
)
```

### Backoff Formula

```
delay = min(max_delay, base_delay * 2^(attempt-1)) + random(0, delay/4)
```

- **Attempt 1**: 1.0s + jitter (0–0.25s)
- **Attempt 2**: 2.0s + jitter (0–0.5s)
- **Attempt 3**: 4.0s + jitter (0–1.0s)

When `circuit_breaker` is provided, `allow_request()` is checked before each attempt. If the circuit is open, `CircuitOpenError` is raised immediately.

---

## Timeout

`call_with_timeout()` wraps an async callable with a hard timeout:

```python
from swx_core.services.llm.resilience import call_with_timeout

try:
    result = await call_with_timeout(
        fn=lambda: provider.generate(request),
        timeout_seconds=60,
        provider_name="openai",
    )
except LLMTimeoutError as e:
    print(f"Provider timed out: {e}")
```

Raises `LLMTimeoutError` (subclass of `TimeoutError`) if the call exceeds `timeout_seconds`.

---

## Configuration

| Setting | Default | Description |
|---|---|---|
| `LLM_CIRCUIT_BREAKER_THRESHOLD` | 5 | Failures before circuit opens |
| `LLM_CIRCUIT_BREAKER_RESET_SECONDS` | 30 | Seconds before half-open |
| `LLM_MAX_RETRIES` | 3 | Max retries for resilient calls |
| `LLM_DEFAULT_TIMEOUT` | 60 | Per-request timeout in seconds |

---

## Usage Examples

### With Circuit Breaker and Retry

```python
from swx_core.services.llm.resilience import (
    CircuitBreakerRegistry, retry_with_backoff, call_with_timeout
)

breaker = CircuitBreakerRegistry.get("openai:gpt-4o")

result = await retry_with_backoff(
    fn=lambda: call_with_timeout(
        fn=lambda: openai_provider.generate(request),
        timeout_seconds=60,
        provider_name="openai",
    ),
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    circuit_breaker=breaker,
)
```

### Monitoring Circuit States

```python
from swx_core.services.llm.resilience import CircuitBreakerRegistry

states = CircuitBreakerRegistry.all_states()
for name, state in states.items():
    if state == "open":
        logger.warning("Circuit OPEN: %s", name)
```