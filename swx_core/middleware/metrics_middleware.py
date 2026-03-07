"""
Prometheus Metrics Middleware for SwX Framework.

Provides comprehensive observability metrics including:
- HTTP request latency histograms
- Request rate counters
- Error rate tracking
- Active request gauge
- Custom business metrics support
"""

import time
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = Info = None

from swx_core.middleware.logging_middleware import logger


# =====================================================
# METRICS DEFINITIONS
# =====================================================

class MetricsConfig:
    """Configuration for metrics collection."""
    
    def __init__(
        self,
        app_name: str = "swx_api",
        enable_default_metrics: bool = True,
        enable_request_size: bool = True,
        enable_response_size: bool = True,
        exclude_paths: Optional[list] = None,
        exclude_methods: Optional[list] = None,
        buckets: Optional[list] = None
    ):
        self.app_name = app_name
        self.enable_default_metrics = enable_default_metrics
        self.enable_request_size = enable_request_size
        self.enable_response_size = enable_response_size
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]
        self.exclude_methods = exclude_methods or ["OPTIONS"]
        self.buckets = buckets or [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]


class PrometheusMetrics:
    """
    Prometheus metrics registry for SwX Framework.
    
    Provides pre-configured metrics for:
    - HTTP requests (latency, count, errors)
    - Active requests gauge
    - Request/response sizes
    - Custom business metrics
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None, registry=None):
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus_client is not installed. "
                "Install it with: pip install prometheus_client"
            )
        
        self.config = config or MetricsConfig()
        self.registry = registry
        
        # Initialize metrics
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all metrics."""
        app_name = self.config.app_name
        
        # HTTP Request Latency
        self.http_request_duration_seconds = Histogram(
            f"{app_name}_http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint", "status_code"],
            buckets=self.config.buckets,
            registry=self.registry
        )
        
        # HTTP Request Count
        self.http_requests_total = Counter(
            f"{app_name}_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry
        )
        
        # Active Requests
        self.http_requests_active = Gauge(
            f"{app_name}_http_requests_active",
            "Number of active HTTP requests",
            ["method"],
            registry=self.registry
        )
        
        # Errors
        self.http_errors_total = Counter(
            f"{app_name}_http_errors_total",
            "Total HTTP errors",
            ["method", "endpoint", "error_type"],
            registry=self.registry
        )
        
        if self.config.enable_request_size:
            self.http_request_size_bytes = Histogram(
                f"{app_name}_http_request_size_bytes",
                "HTTP request size in bytes",
                ["method", "endpoint"],
                buckets=[100, 1000, 10000, 100000, 1000000],
                registry=self.registry
            )
        
        if self.config.enable_response_size:
            self.http_response_size_bytes = Histogram(
                f"{app_name}_http_response_size_bytes",
                "HTTP response size in bytes",
                ["method", "endpoint"],
                buckets=[100, 1000, 10000, 100000, 1000000],
                registry=self.registry
            )
        
        # Database Metrics
        self.db_query_duration_seconds = Histogram(
            f"{app_name}_db_query_duration_seconds",
            "Database query latency in seconds",
            ["operation", "table"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.db_connections_active = Gauge(
            f"{app_name}_db_connections_active",
            "Active database connections",
            registry=self.registry
        )
        
        # Cache Metrics
        self.cache_hits_total = Counter(
            f"{app_name}_cache_hits_total",
            "Total cache hits",
            ["cache_name"],
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            f"{app_name}_cache_misses_total",
            "Total cache misses",
            ["cache_name"],
            registry=self.registry
        )
        
        # Authentication Metrics
        self.auth_attempts_total = Counter(
            f"{app_name}_auth_attempts_total",
            "Total authentication attempts",
            ["method", "result"],
            registry=self.registry
        )
        
        self.auth_failures_total = Counter(
            f"{app_name}_auth_failures_total",
            "Total authentication failures",
            ["reason"],
            registry=self.registry
        )
        
        # Business Metrics
        self.business_operations_total = Counter(
            f"{app_name}_business_operations_total",
            "Total business operations",
            ["operation", "status"],
            registry=self.registry
        )
        
        # Application Info
        self.app_info = Info(
            f"{app_name}_app_info",
            "Application information",
            registry=self.registry
        )


# Global metrics instance
_metrics_instance: Optional[PrometheusMetrics] = None
_config: Optional[MetricsConfig] = None


def get_metrics() -> Optional[PrometheusMetrics]:
    """Get the global metrics instance."""
    return _metrics_instance


def init_metrics(config: Optional[MetricsConfig] = None) -> PrometheusMetrics:
    """
    Initialize the global metrics instance.
    
    Args:
        config: Metrics configuration
        
    Returns:
        PrometheusMetrics: The initialized metrics instance
    """
    global _metrics_instance, _config
    _config = config or MetricsConfig()
    
    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "prometheus_client not installed. Metrics collection disabled. "
            "Install with: pip install prometheus_client"
        )
        return None
    
    _metrics_instance = PrometheusMetrics(_config)
    return _metrics_instance


# =====================================================
# MIDDLEWARE
# =====================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic Prometheus metrics collection.
    
    Usage:
        from swx_core.middleware.metrics_middleware import MetricsMiddleware, init_metrics
        
        # Initialize metrics
        metrics = init_metrics(MetricsConfig(app_name="my_app"))
        
        # Add middleware to FastAPI app
        app = FastAPI()
        app.add_middleware(MetricsMiddleware, metrics=metrics)
        
        # Expose metrics endpoint
        @app.get("/metrics")
        async def metrics_endpoint():
            return Response(
                content=generate_latest(metrics.registry),
                media_type=CONTENT_TYPE_LATEST
            )
    """
    
    def __init__(
        self,
        app: ASGIApp,
        metrics: Optional[PrometheusMetrics] = None,
        config: Optional[MetricsConfig] = None
    ):
        super().__init__(app)
        self.metrics = metrics or get_metrics()
        self.config = config or _config or MetricsConfig()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and record metrics."""
        
        # Skip excluded paths
        if request.url.path in self.config.exclude_paths:
            return await call_next(request)
        
        # Skip excluded methods
        if request.method in self.config.exclude_methods:
            return await call_next(request)
        
        # Skip if metrics not initialized
        if not self.metrics:
            return await call_next(request)
        
        # Get normalized endpoint path (replace path params with placeholders)
        endpoint = self._get_endpoint_pattern(request)
        method = request.method
        
        # Track active requests
        self.metrics.http_requests_active.labels(method=method).inc()
        
        # Record request start time
        start_time = time.perf_counter()
        
        # Track request size
        request_size = request.headers.get("content-length")
        if request_size and self.config.enable_request_size:
            try:
                self.metrics.http_request_size_bytes.labels(
                    method=method, endpoint=endpoint
                ).observe(int(request_size))
            except (ValueError, TypeError):
                pass
        
        try:
            response = await call_next(request)
            
            # Record latency
            duration = time.perf_counter() - start_time
            self.metrics.http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(response.status_code)
            ).observe(duration)
            
            # Increment request counter
            self.metrics.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(response.status_code)
            ).inc()
            
            # Track response size
            response_size = response.headers.get("content-length")
            if response_size and self.config.enable_response_size:
                try:
                    self.metrics.http_response_size_bytes.labels(
                        method=method, endpoint=endpoint
                    ).observe(int(response_size))
                except (ValueError, TypeError):
                    pass
            
            # Track errors (4xx and 5xx)
            if response.status_code >= 400:
                error_type = "client_error" if response.status_code < 500 else "server_error"
                self.metrics.http_errors_total.labels(
                    method=method,
                    endpoint=endpoint,
                    error_type=error_type
                ).inc()
            
            return response
            
        except Exception as e:
            # Record error
            self.metrics.http_errors_total.labels(
                method=method,
                endpoint=endpoint,
                error_type="exception"
            ).inc()
            
            self.metrics.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code="500"
            ).inc()
            
            raise
            
        finally:
            # Decrement active requests
            self.metrics.http_requests_active.labels(method=method).dec()
    
    def _get_endpoint_pattern(self, request: Request) -> str:
        """
        Get a normalized endpoint path for metrics.
        
        Replaces path parameters with placeholders to avoid
        high cardinality labels.
        
        Example:
            /users/123 -> /users/{id}
            /posts/456/comments -> /posts/{id}/comments
        """
        path = request.url.path
        
        # Get route pattern if available (from Starlette/FastAPI routing)
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope.get("route")
            if route and hasattr(route, "path"):
                return route.path
        
        # Fallback: normalize numeric path segments
        import re
        segments = path.split("/")
        normalized = []
        
        for segment in segments:
            if segment.isdigit():
                normalized.append("{id}")
            elif re.match(r'^[a-f0-9-]{36}$', segment):  # UUID
                normalized.append("{uuid}")
            else:
                normalized.append(segment)
        
        return "/".join(normalized)


# =====================================================
# HELPER FUNCTIONS FOR CUSTOM METRICS
# =====================================================

def record_db_query(operation: str, table: str, duration: float):
    """Record a database query metric."""
    metrics = get_metrics()
    if metrics:
        metrics.db_query_duration_seconds.labels(
            operation=operation,
            table=table
        ).observe(duration)


def record_cache_hit(cache_name: str):
    """Record a cache hit."""
    metrics = get_metrics()
    if metrics:
        metrics.cache_hits_total.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str):
    """Record a cache miss."""
    metrics = get_metrics()
    if metrics:
        metrics.cache_misses_total.labels(cache_name=cache_name).inc()


def record_auth_attempt(method: str, result: str):
    """Record an authentication attempt."""
    metrics = get_metrics()
    if metrics:
        metrics.auth_attempts_total.labels(method=method, result=result).inc()


def record_auth_failure(reason: str):
    """Record an authentication failure."""
    metrics = get_metrics()
    if metrics:
        metrics.auth_failures_total.labels(reason=reason).inc()


def record_business_operation(operation: str, status: str):
    """Record a business operation."""
    metrics = get_metrics()
    if metrics:
        metrics.business_operations_total.labels(
            operation=operation, status=status
        ).inc()


def set_app_info(version: str, environment: str, extra: dict = None):
    """Set application information."""
    metrics = get_metrics()
    if metrics:
        info = {"version": version, "environment": environment}
        if extra:
            info.update(extra)
        metrics.app_info.info(info)


def set_app_info(version: str, environment: str, extra: dict = None):
    """Set application information."""
    metrics = get_metrics()
    if metrics:
        info = {"version": version, "environment": environment}
        if extra:
            info.update(extra)
        metrics.app_info.info(info)


def apply_middleware(app):
    """
    Apply Prometheus metrics middleware (called by dynamic middleware loader).
    
    This function is called automatically by swx_core.utils.loader.load_middleware().
    It initializes metrics and adds the MetricsMiddleware to the FastAPI app.
    
    Args:
        app: The FastAPI application instance.
    
    Usage:
        The middleware is automatically applied when swx_core starts.
        To enable Prometheus metrics, ensure prometheus_client is installed:
        
        pip install prometheus_client
        
        Metrics will be available at /metrics endpoint if you add:
        
        @app.get("/metrics")
        async def metrics_endpoint():
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            metrics = get_metrics()
            if metrics:
                return Response(
                    content=generate_latest(metrics.registry),
                    media_type=CONTENT_TYPE_LATEST
                )
            return {"error": "Metrics not initialized"}
    """
    # Skip if Prometheus is not available
    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "prometheus_client not installed. Metrics middleware disabled. "
            "Install with: pip install prometheus_client"
        )
        return
    
    # Initialize metrics with default config
    metrics = init_metrics()
    
    if metrics:
        app.add_middleware(MetricsMiddleware, metrics=metrics)
        logger.info("Prometheus metrics middleware enabled")