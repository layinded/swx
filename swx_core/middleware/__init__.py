"""
SwX Middleware Module.

Provides middleware for:
- CORS handling
- Session management
- Rate limiting
- Audit logging
- Request logging
- Metrics collection
- Sentry error tracking
"""

from swx_core.middleware.cors_middleware import (
    setup_cors_middleware,
    apply_middleware as apply_cors_middleware,
)
from swx_core.middleware.session_middleware import (
    SessionMiddleware,
    setup_session_middleware,
)
from swx_core.middleware.rate_limit_middleware import RateLimitMiddleware
from swx_core.middleware.audit_middleware import AuditMiddleware, apply_middleware as apply_audit_middleware
from swx_core.middleware.logging_middleware import logger
from swx_core.middleware.sentry_middleware import (
    setup_sentry_middleware,
    apply_middleware as apply_sentry_middleware,
)

try:
    from swx_core.middleware.metrics_middleware import (
        MetricsMiddleware,
        PrometheusMetrics,
        MetricsConfig,
        init_metrics,
        get_metrics,
        record_db_query,
        record_cache_hit,
        record_cache_miss,
        record_auth_attempt,
        record_auth_failure,
        record_business_operation,
        set_app_info,
        apply_middleware as apply_metrics_middleware,
        PROMETHEUS_AVAILABLE
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    MetricsMiddleware = None
    PrometheusMetrics = None
    MetricsConfig = None
    apply_metrics_middleware = None
    init_metrics = None
    get_metrics = None
    record_db_query = None
    record_cache_hit = None
    record_cache_miss = None
    record_auth_attempt = None
    record_auth_failure = None
    record_business_operation = None
    set_app_info = None

__all__ = [
    # CORS
    "setup_cors_middleware",
    "apply_cors_middleware",
    
    # Session
    "SessionMiddleware",
    "setup_session_middleware",
    
    # Rate Limiting
    "RateLimitMiddleware",
    
    # Audit
    "AuditMiddleware",
    "apply_audit_middleware",
    
    # Logging
    "logger",
    
    # Sentry
    "setup_sentry_middleware",
    "apply_sentry_middleware",
    
    # Metrics (optional)
    "MetricsMiddleware",
    "PrometheusMetrics",
    "MetricsConfig",
    "init_metrics",
    "get_metrics",
    "record_db_query",
    "record_cache_hit",
    "record_cache_miss",
    "record_auth_attempt",
    "record_auth_failure",
    "record_business_operation",
    "set_app_info",
    "apply_metrics_middleware",
    "PROMETHEUS_AVAILABLE",
]