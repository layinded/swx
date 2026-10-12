# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Prometheus Metrics Middleware for SwX Framework — pure ASGI, SSE-safe.

Provides comprehensive observability metrics including:
- HTTP request latency histograms
- Request rate counters
- Error rate tracking
- Active request gauge
- Custom business metrics support

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.
"""

import re
import time
from typing import Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = Info = None  # type: ignore[assignment,misc]

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

        self._init_metrics()

    def _init_metrics(self):
        """Initialize all metrics."""
        app_name = self.config.app_name

        self.http_request_duration_seconds = Histogram(
            f"{app_name}_http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint", "status_code"],
            buckets=self.config.buckets,
            registry=self.registry
        )

        self.http_requests_total = Counter(
            f"{app_name}_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry
        )

        self.http_requests_active = Gauge(
            f"{app_name}_http_requests_active",
            "Number of active HTTP requests",
            ["method"],
            registry=self.registry
        )

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

        self.business_operations_total = Counter(
            f"{app_name}_business_operations_total",
            "Total business operations",
            ["operation", "status"],
            registry=self.registry
        )

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


def init_metrics(config: Optional[MetricsConfig] = None) -> Optional[PrometheusMetrics]:
    """Initialize the global metrics instance."""
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

_UUID_RE = re.compile(r'^[a-f0-9-]{36}$')


def _get_endpoint_pattern(scope: Scope) -> str:
    """Normalise path for metrics labels (replace numeric/UUID segments)."""
    # Prefer route pattern from Starlette/FastAPI routing
    route = scope.get("route")
    if route and hasattr(route, "path"):
        return route.path

    path = scope.get("path", "/")
    segments = path.split("/")
    normalized = []
    for segment in segments:
        if segment.isdigit():
            normalized.append("{id}")
        elif _UUID_RE.match(segment):
            normalized.append("{uuid}")
        else:
            normalized.append(segment)
    return "/".join(normalized)


class MetricsMiddleware:
    """Pure-ASGI Prometheus metrics middleware — SSE-safe.

    Records latency, request count, error rate, and active request gauge
    by intercepting ``http.response.start`` instead of buffering the
    response body via BaseHTTPMiddleware.
    """

    def __init__(
        self,
        app: ASGIApp,
        metrics: Optional[PrometheusMetrics] = None,
        config: Optional[MetricsConfig] = None
    ):
        self.app = app
        self.metrics = metrics or get_metrics()
        self.config = config or _config or MetricsConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Skip excluded paths and methods
        if path in self.config.exclude_paths:
            await self.app(scope, receive, send)
            return

        if method in self.config.exclude_methods:
            await self.app(scope, receive, send)
            return

        # Skip if metrics not initialized
        if not self.metrics:
            await self.app(scope, receive, send)
            return

        endpoint = _get_endpoint_pattern(scope)

        # Track active requests
        self.metrics.http_requests_active.labels(method=method).inc()

        # Record request size from header
        headers_list: list[tuple[bytes, bytes]] = scope.get("headers", [])
        request_size = None
        for k, v in headers_list:
            if k.lower() == b"content-length":
                try:
                    request_size = int(v)
                except (ValueError, TypeError):
                    pass
                break

        if request_size is not None and self.config.enable_request_size:
            try:
                self.metrics.http_request_size_bytes.labels(
                    method=method, endpoint=endpoint
                ).observe(request_size)
            except (ValueError, TypeError):
                pass

        start_time = time.perf_counter()

        async def send_with_metrics(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code = str(message.get("status", 0))
                duration = time.perf_counter() - start_time

                # Record latency
                self.metrics.http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code
                ).observe(duration)

                # Increment request counter
                self.metrics.http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code
                ).inc()

                # Track response size from header
                if self.config.enable_response_size:
                    for k, v in message.get("headers", []):
                        if k.lower() == b"content-length":
                            try:
                                self.metrics.http_response_size_bytes.labels(
                                    method=method, endpoint=endpoint
                                ).observe(int(v))
                            except (ValueError, TypeError):
                                pass
                            break

                # Track errors (4xx and 5xx)
                code_int = int(status_code)
                if code_int >= 400:
                    error_type = "client_error" if code_int < 500 else "server_error"
                    self.metrics.http_errors_total.labels(
                        method=method,
                        endpoint=endpoint,
                        error_type=error_type
                    ).inc()

            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        except Exception:
            # Record unhandled exception
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
            self.metrics.http_requests_active.labels(method=method).dec()


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


def apply_middleware(app):
    """Apply Prometheus metrics middleware (called by dynamic middleware loader).

    Initializes metrics and adds MetricsMiddleware to the FastAPI app.
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "prometheus_client not installed. Metrics middleware disabled. "
            "Install with: pip install prometheus_client"
        )
        return

    metrics = init_metrics()

    if metrics:
        app.add_middleware(MetricsMiddleware, metrics=metrics)
        logger.info("Prometheus metrics middleware enabled")