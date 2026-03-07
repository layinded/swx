"""
SwX Middleware Module.

Provides middleware for:
- CORS handling
- Session management
- Rate limiting
- Audit logging
- Request logging
- Metrics collection
"""

from swx_core.middleware.cors_middleware import *
from swx_core.middleware.session_middleware import *
from swx_core.middleware.rate_limit_middleware import *
from swx_core.middleware.audit_middleware import *
from swx_core.middleware.logging_middleware import *
from swx_core.middleware.sentry_middleware import *

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
        PROMETHEUS_AVAILABLE
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    MetricsMiddleware = None
    PrometheusMetrics = None
    MetricsConfig = None

__all__ = [
    # CORS
    "CORS_MIDDLEWARE",
    
    # Session
    "SessionMiddleware",
    
    # Rate Limiting
    "RateLimitMiddleware",
    
    # Audit
    "AuditMiddleware",
    
    # Logging
    "logger",
    
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
    "PROMETHEUS_AVAILABLE",
]