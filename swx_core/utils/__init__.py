"""
SwX Utilities Package
----------------------
Provides common utilities, helpers and base classes.
"""

# Pagination
from swx_core.utils.pagination import (
    PaginationParams,
    PaginatedResponse,
    CursorPaginationParams,
    CursorPaginatedResponse,
    OffsetPaginationParams,
    PaginationMeta,
    paginate,
    calculate_pagination,
)

# Response utilities
from swx_core.utils.response import (
    APIResponse,
    DataResponse,
    ErrorResponse,
    ValidationError as ValidationErrorDetail,
    ValidationErrorResponse,
    SuccessResponse,
    DeleteResponse,
    BatchResponse,
    HealthResponse,
    PagedResponse,
    success,
    error,
    validation_error,
)

# Caching
from swx_core.utils.cache import (
    CacheBackend,
    MemoryCache,
    RedisCache,
    get_cache,
    set_cache,
    init_redis_cache,
    cached,
    cache_result,
    invalidate_cache,
    memoize,
)

# Validation
from swx_core.utils.validators import (
    validate_model,
    validate_email,
    validate_phone,
    validate_password,
    validate_unique,
    validate_required,
    validate_min_value,
    validate_max_value,
    validate_length,
    validate_regex,
    validate_in,
)

# Model mixins
from swx_core.utils.mixins import (
    TimestampMixin,
    SoftDeleteMixin,
    UUIDPrimaryKeyMixin,
    CreatedByMixin,
    UpdatedByMixin,
    AuditMixin,
    ActiveMixin,
    SlugMixin,
    TitleMixin,
    DescriptionMixin,
    MetadataMixin,
    FullModelMixin,
    AuditedModelMixin,
)

# Testing
from swx_core.utils.testing import (
    TestSession,
    TestDatabase,
    TestClientWithDB,
    ModelFactory,
    AsyncTestMixin,
    random_uuid,
    random_email,
    random_string,
    assert_response_status,
    assert_response_json,
    assert_model_equal,
    create_fixture_data,
)

# Rate limiting
from swx_core.utils.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    get_rate_limiter,
    set_rate_limiter,
    rate_limit,
    rate_limit_by_ip,
    rate_limit_by_user,
    rate_limit_by_api_key,
    check_rate_limit,
)

# Query builder
from swx_core.utils.query import (
    QueryBuilder,
    SortOrder,
)

# Error handling
from swx_core.utils.errors import (
    SwXError,
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    ConflictError,
    RateLimitError,
    ServiceUnavailableError,
    DatabaseError,
    ExternalServiceError,
    ConfigurationError,
    not_found,
    unauthorized,
    forbidden,
    bad_request,
    conflict,
    rate_limited,
    service_unavailable,
)

# Dependency injection
from swx_core.utils.dependencies import (
    inject,
    inject_service,
    get_current_user,
    get_current_user_optional,
    require_roles,
    require_permissions,
    require_superuser,
    require_ownership,
    get_pagination_params,
    get_request_id,
    get_client_ip,
    AuthDependencies,
    CommonDependencies,
)

# Health checks
from swx_core.utils.health import (
    HealthStatus,
    HealthCheckResult,
    HealthChecker,
    check_database,
    check_redis,
    check_celery,
    check_external_service,
    get_health_checker,
    setup_health_checker,
)

# Unit of Work
from swx_core.utils.unit_of_work import (
    UnitOfWork,
    UnitOfWorkManager,
    uow,
    with_unit_of_work,
    Transactional,
    transactional,
)

# Filters
from swx_core.utils.filters import (
    FilterOperator,
    FilterCondition,
    FilterBuilder,
    SortBuilder,
    FilterParams,
)

# Versioning
from swx_core.utils.versioning import (
    VersionStatus,
    VersionInfo,
    parse_version,
    compare_versions,
    get_latest_version,
    is_valid_version,
    get_version_status,
    set_version_status,
    DeprecationWarningMiddleware,
    deprecated_version,
    create_versioned_router,
    version_route,
    negotiate_version,
    VersionedRouter,
    list_versions,
    check_version_compatibility,
)

__all__ = [
    # Pagination
    "PaginationParams",
    "PaginatedResponse",
    "CursorPaginationParams",
    "CursorPaginatedResponse",
    "OffsetPaginationParams",
    "PaginationMeta",
    "paginate",
    "calculate_pagination",
    
    # Response
    "APIResponse",
    "DataResponse",
    "ErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    "SuccessResponse",
    "DeleteResponse",
    "BatchResponse",
    "HealthResponse",
    "PagedResponse",
    "success",
    "error",
    "validation_error",
    
    # Cache
    "CacheBackend",
    "MemoryCache",
    "RedisCache",
    "get_cache",
    "set_cache",
    "init_redis_cache",
    "cached",
    "cache_result",
    "invalidate_cache",
    "memoize",
    
    # Validators
    "validate_model",
    "validate_email",
    "validate_phone",
    "validate_password",
    "validate_unique",
    "validate_required",
    "validate_min_value",
    "validate_max_value",
    "validate_length",
    "validate_regex",
    "validate_in",
    
    # Mixins
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDPrimaryKeyMixin",
    "CreatedByMixin",
    "UpdatedByMixin",
    "AuditMixin",
    "ActiveMixin",
    "SlugMixin",
    "TitleMixin",
    "DescriptionMixin",
    "MetadataMixin",
    "FullModelMixin",
    "AuditedModelMixin",
    
    # Testing
    "TestSession",
    "TestDatabase",
    "TestClientWithDB",
    "ModelFactory",
    "AsyncTestMixin",
    "random_uuid",
    "random_email",
    "random_string",
    "assert_response_status",
    "assert_response_json",
    "assert_model_equal",
    "create_fixture_data",
    
    # Rate Limiting
    "RateLimiter",
    "RateLimitExceeded",
    "get_rate_limiter",
    "set_rate_limiter",
    "rate_limit",
    "rate_limit_by_ip",
    "rate_limit_by_user",
    "rate_limit_by_api_key",
    "check_rate_limit",
    
    # Query Builder
    "QueryBuilder",
    "SortOrder",
    
    # Error handling
    "SwXError",
    "ValidationError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "RateLimitError",
    "ServiceUnavailableError",
    "DatabaseError",
    "ExternalServiceError",
    "ConfigurationError",
    "not_found",
    "unauthorized",
    "forbidden",
    "bad_request",
    "conflict",
    "rate_limited",
    "service_unavailable",
    
    # Dependency injection
    "inject",
    "inject_service",
    "get_current_user",
    "get_current_user_optional",
    "require_roles",
    "require_permissions",
    "require_superuser",
    "require_ownership",
    "get_pagination_params",
    "get_request_id",
    "get_client_ip",
    "AuthDependencies",
    "CommonDependencies",
    
    # Health checks
    "HealthStatus",
    "HealthCheckResult",
    "HealthChecker",
    "check_database",
    "check_redis",
    "check_celery",
    "check_external_service",
    "get_health_checker",
    "setup_health_checker",
    
    # Unit of Work
    "UnitOfWork",
    "UnitOfWorkManager",
    "uow",
    "with_unit_of_work",
    "Transactional",
    "transactional",
    
    # Filters
    "FilterOperator",
    "FilterCondition",
    "FilterBuilder",
    "SortBuilder",
    "FilterParams",
    
    # Versioning
    "VersionStatus",
    "VersionInfo",
    "parse_version",
    "compare_versions",
    "get_latest_version",
    "is_valid_version",
    "get_version_status",
    "set_version_status",
    "DeprecationWarningMiddleware",
    "deprecated_version",
    "create_versioned_router",
    "version_route",
    "negotiate_version",
    "VersionedRouter",
    "list_versions",
    "check_version_compatibility",
]