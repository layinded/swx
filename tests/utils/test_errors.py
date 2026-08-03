# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.utils.errors — exception hierarchy and convenience functions."""

import pytest
from fastapi import status

from swx_core.utils.errors import (
    ConfigurationError,
    ConflictError,
    DatabaseError,
    DecryptionError,
    EncryptionError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    PolicyViolationError,
    QuotaExceededError,
    RateLimitError,
    ServiceUnavailableError,
    SwXError,
    UnauthorizedError,
    ValidationError,
    bad_request,
    conflict,
    forbidden,
    not_found,
    rate_limited,
    service_unavailable,
    unauthorized,
)


# ---------------------------------------------------------------------------
# SwXError
# ---------------------------------------------------------------------------

class TestSwXError:
    """Tests for the base SwXError class."""

    def test_default_values(self) -> None:
        """Default constructor values are sensible."""
        err = SwXError()
        assert err.message == "An error occurred"
        assert err.code == "ERROR"
        assert err.details == {}
        assert err.status_code == status.HTTP_400_BAD_REQUEST

    def test_custom_values(self) -> None:
        """Custom values are stored correctly."""
        err = SwXError(
            message="Custom error",
            code="CUSTOM",
            details={"key": "value"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        assert err.message == "Custom error"
        assert err.code == "CUSTOM"
        assert err.details == {"key": "value"}
        assert err.status_code == 500

    def test_to_dict_format(self) -> None:
        """to_dict() returns the expected structure."""
        err = SwXError(message="Something broke", code="BREAK", details={"info": "x"})
        d = err.to_dict()
        assert d == {
            "success": False,
            "error": {
                "code": "BREAK",
                "message": "Something broke",
                "details": {"info": "x"},
            },
        }

    def test_to_dict_default_details(self) -> None:
        """to_dict() with default details returns empty dict."""
        err = SwXError(message="msg", code="ERR")
        d = err.to_dict()
        assert d["error"]["details"] == {}

    def test_str_representation(self) -> None:
        """str() returns the message."""
        err = SwXError(message="test message")
        assert str(err) == "test message"


# ---------------------------------------------------------------------------
# EncryptionError / DecryptionError
# ---------------------------------------------------------------------------

class TestEncryptionErrors:
    """Tests for EncryptionError and DecryptionError hierarchy."""

    def test_encryption_error_is_value_error(self) -> None:
        """EncryptionError is a subclass of ValueError."""
        err = EncryptionError("bad key")
        assert isinstance(err, ValueError)
        assert isinstance(err, Exception)

    def test_decryption_error_is_encryption_error(self) -> None:
        """DecryptionError is a subclass of EncryptionError."""
        err = DecryptionError("bad ciphertext")
        assert isinstance(err, EncryptionError)
        assert isinstance(err, ValueError)

    def test_encryption_error_message(self) -> None:
        """EncryptionError stores and displays the message."""
        err = EncryptionError("encryption failed")
        assert err.message == "encryption failed"
        assert str(err) == "encryption failed"

    def test_decryption_error_message(self) -> None:
        """DecryptionError stores and displays the message."""
        err = DecryptionError("decryption failed")
        assert err.message == "decryption failed"
        assert str(err) == "decryption failed"

    def test_default_messages(self) -> None:
        """Default messages are set when none provided."""
        assert EncryptionError().message == "Encryption error"
        assert DecryptionError().message == "Decryption error"


# ---------------------------------------------------------------------------
# QuotaExceededError
# ---------------------------------------------------------------------------

class TestQuotaExceededError:
    """Tests for QuotaExceededError."""

    def test_default_values(self) -> None:
        """Default constructor values."""
        err = QuotaExceededError()
        assert err.message == "Quota exceeded"
        assert err.code == "QUOTA_EXCEEDED"
        assert err.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert err.details == {}

    def test_with_resource(self) -> None:
        """Resource detail is included in details."""
        err = QuotaExceededError(resource="tokens")
        assert err.details == {"resource": "tokens"}

    def test_custom_message(self) -> None:
        """Custom message is stored."""
        err = QuotaExceededError(message="Token limit reached", resource="daily_tokens")
        assert err.message == "Token limit reached"
        assert err.details == {"resource": "daily_tokens"}

    def test_to_dict_includes_resource(self) -> None:
        """to_dict() includes resource in details."""
        err = QuotaExceededError(resource="api_calls")
        d = err.to_dict()
        assert d["error"]["details"] == {"resource": "api_calls"}


# ---------------------------------------------------------------------------
# PolicyViolationError
# ---------------------------------------------------------------------------

class TestPolicyViolationError:
    """Tests for PolicyViolationError."""

    def test_default_values(self) -> None:
        """Default constructor values."""
        err = PolicyViolationError()
        assert err.message == "Policy violation"
        assert err.code == "POLICY_VIOLATION"
        assert err.status_code == status.HTTP_403_FORBIDDEN

    def test_with_policy(self) -> None:
        """Policy detail is included in details."""
        err = PolicyViolationError(policy="content_filter")
        assert err.details == {"policy": "content_filter"}

    def test_custom_message(self) -> None:
        """Custom message is stored."""
        err = PolicyViolationError(message="Blocked by safety filter", policy="profanity_filter")
        assert err.message == "Blocked by safety filter"
        assert err.details == {"policy": "profanity_filter"}

    def test_to_dict_includes_policy(self) -> None:
        """to_dict() includes policy in details."""
        err = PolicyViolationError(policy="rate_limit_policy")
        d = err.to_dict()
        assert d["error"]["details"] == {"policy": "rate_limit_policy"}


# ---------------------------------------------------------------------------
# Other exception subclasses
# ---------------------------------------------------------------------------

class TestExceptionSubclasses:
    """Tests for the remaining exception subclasses."""

    def test_validation_error(self) -> None:
        """ValidationError has correct code and status."""
        err = ValidationError(message="Invalid input", errors=[{"field": "name", "msg": "required"}])
        assert err.code == "VALIDATION_ERROR"
        assert err.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert err.details == {"errors": [{"field": "name", "msg": "required"}]}

    def test_not_found_error(self) -> None:
        """NotFoundError formats the resource name."""
        err = NotFoundError(resource="User", resource_id="123")
        assert err.code == "NOT_FOUND"
        assert err.status_code == status.HTTP_404_NOT_FOUND
        assert "User" in err.message
        assert "123" in err.message

    def test_not_found_error_without_id(self) -> None:
        """NotFoundError without resource_id."""
        err = NotFoundError(resource="User")
        assert err.message == "User not found"

    def test_unauthorized_error(self) -> None:
        """UnauthorizedError has correct code and status."""
        err = UnauthorizedError(message="Invalid token")
        assert err.code == "UNAUTHORIZED"
        assert err.status_code == status.HTTP_401_UNAUTHORIZED

    def test_forbidden_error(self) -> None:
        """ForbiddenError includes permission detail."""
        err = ForbiddenError(message="Access denied", permission="admin:write")
        assert err.code == "FORBIDDEN"
        assert err.status_code == status.HTTP_403_FORBIDDEN
        assert err.details == {"permission": "admin:write"}

    def test_conflict_error(self) -> None:
        """ConflictError includes resource detail."""
        err = ConflictError(message="Already exists", resource="User")
        assert err.code == "CONFLICT"
        assert err.status_code == status.HTTP_409_CONFLICT
        assert err.details == {"resource": "User"}

    def test_rate_limit_error(self) -> None:
        """RateLimitError includes retry_after."""
        err = RateLimitError(retry_after=120)
        assert err.code == "RATE_LIMIT_EXCEEDED"
        assert err.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert err.details == {"retry_after": 120}

    def test_service_unavailable_error(self) -> None:
        """ServiceUnavailableError includes service detail."""
        err = ServiceUnavailableError(service="redis")
        assert err.code == "SERVICE_UNAVAILABLE"
        assert err.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert err.details == {"service": "redis"}

    def test_database_error(self) -> None:
        """DatabaseError includes operation detail."""
        err = DatabaseError(message="Connection failed", operation="connect")
        assert err.code == "DATABASE_ERROR"
        assert err.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert err.details == {"operation": "connect"}

    def test_external_service_error(self) -> None:
        """ExternalServiceError includes service name."""
        err = ExternalServiceError(service="stripe", message="Payment failed")
        assert err.code == "EXTERNAL_SERVICE_ERROR"
        assert err.status_code == status.HTTP_502_BAD_GATEWAY
        assert err.details == {"service": "stripe"}

    def test_configuration_error(self) -> None:
        """ConfigurationError has correct code and status."""
        err = ConfigurationError(message="Missing required setting")
        assert err.code == "CONFIGURATION_ERROR"
        assert err.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for the HTTP exception convenience functions."""

    def test_not_found_raises(self) -> None:
        """not_found() raises NotFoundError."""
        with pytest.raises(NotFoundError, match="User with id '42' not found"):
            not_found(resource="User", resource_id="42")

    def test_unauthorized_raises(self) -> None:
        """unauthorized() raises UnauthorizedError."""
        with pytest.raises(UnauthorizedError, match="Invalid credentials"):
            unauthorized(message="Invalid credentials")

    def test_forbidden_raises(self) -> None:
        """forbidden() raises ForbiddenError."""
        with pytest.raises(ForbiddenError, match="No access"):
            forbidden(message="No access", permission="admin:write")

    def test_bad_request_raises(self) -> None:
        """bad_request() raises SwXError with BAD_REQUEST code."""
        with pytest.raises(SwXError) as exc_info:
            bad_request(message="Missing field", details={"field": "email"})
        assert exc_info.value.code == "BAD_REQUEST"
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.details == {"field": "email"}

    def test_bad_request_defaults(self) -> None:
        """bad_request() with no arguments uses defaults."""
        with pytest.raises(SwXError) as exc_info:
            bad_request()
        assert exc_info.value.message == "Bad request"
        assert exc_info.value.details == {}

    def test_conflict_raises(self) -> None:
        """conflict() raises ConflictError."""
        with pytest.raises(ConflictError, match="Duplicate entry"):
            conflict(message="Duplicate entry", resource="User")

    def test_rate_limited_raises(self) -> None:
        """rate_limited() raises RateLimitError."""
        with pytest.raises(RateLimitError) as exc_info:
            rate_limited(retry_after=30)
        assert exc_info.value.details == {"retry_after": 30}

    def test_service_unavailable_raises(self) -> None:
        """service_unavailable() raises ServiceUnavailableError."""
        with pytest.raises(ServiceUnavailableError) as exc_info:
            service_unavailable(service="database", message="Down for maintenance")
        assert exc_info.value.details == {"service": "database"}
