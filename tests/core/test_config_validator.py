import os

import pytest

from swx_core.config.validator import ProductionValidator


class TestProductionValidatorRequire:
    def test_require_fails_on_missing_env(self):
        os.environ.pop("_TEST_MISSING_VAR", None)
        v = ProductionValidator()
        v.require("_TEST_MISSING_VAR")
        errors = v.validate(environment="production")
        assert len(errors) == 1
        assert "_TEST_MISSING_VAR" in errors[0]

    def test_require_fails_on_empty_env(self):
        os.environ["_TEST_EMPTY_VAR"] = ""
        v = ProductionValidator()
        v.require("_TEST_EMPTY_VAR")
        errors = v.validate(environment="production")
        assert len(errors) == 1

    def test_require_passes_on_set_env(self):
        os.environ["_TEST_SET_VAR"] = "real_value"
        v = ProductionValidator()
        v.require("_TEST_SET_VAR")
        errors = v.validate(environment="production")
        assert errors == []
        del os.environ["_TEST_SET_VAR"]

    def test_require_fails_on_placeholder(self):
        for placeholder in ["<KEY>", "${VAR}", "$MY_VAR", "sk_test_mock123", "pk_test_mock456", "whsec_mock789"]:
            os.environ["_TEST_PH"] = placeholder
            v = ProductionValidator()
            v.require("_TEST_PH")
            errors = v.validate(environment="production")
            assert len(errors) == 1, f"Placeholder '{placeholder}' should be rejected"
        os.environ.pop("_TEST_PH", None)

    def test_require_skipped_in_non_production(self):
        os.environ.pop("_TEST_MISSING_VAR", None)
        v = ProductionValidator()
        v.require("_TEST_MISSING_VAR")
        for env in ["local", "staging", "test", "development"]:
            errors = v.validate(environment=env)
            assert errors == [], f"Validation should be skipped in {env}"


class TestProductionValidatorForbidLocalhost:
    def test_forbid_localhost_fails_on_localhost(self):
        os.environ["_TEST_URL"] = "http://localhost:3000"
        v = ProductionValidator()
        v.forbid_localhost("_TEST_URL")
        errors = v.validate(environment="production")
        assert len(errors) == 1
        del os.environ["_TEST_URL"]

    def test_forbid_localhost_fails_on_127(self):
        os.environ["_TEST_URL"] = "http://127.0.0.1:3000"
        v = ProductionValidator()
        v.forbid_localhost("_TEST_URL")
        errors = v.validate(environment="production")
        assert len(errors) == 1
        del os.environ["_TEST_URL"]

    def test_forbid_localhost_fails_on_0000(self):
        os.environ["_TEST_URL"] = "http://0.0.0.0:8080"
        v = ProductionValidator()
        v.forbid_localhost("_TEST_URL")
        errors = v.validate(environment="production")
        assert len(errors) == 1
        del os.environ["_TEST_URL"]

    def test_forbid_localhost_passes_on_real_url(self):
        os.environ["_TEST_URL"] = "https://api.example.com"
        v = ProductionValidator()
        v.forbid_localhost("_TEST_URL")
        errors = v.validate(environment="production")
        assert errors == []
        del os.environ["_TEST_URL"]


class TestProductionValidatorCheck:
    def test_check_fails_when_condition_false(self):
        v = ProductionValidator()
        v.check(lambda: False, "Condition X must hold")
        errors = v.validate(environment="production")
        assert len(errors) == 1
        assert "Condition X must hold" in errors[0]

    def test_check_passes_when_condition_true(self):
        v = ProductionValidator()
        v.check(lambda: True, "Should not appear")
        errors = v.validate(environment="production")
        assert errors == []


class TestProductionValidatorChaining:
    def test_chainable_api(self):
        v = ProductionValidator()
        result = v.require("A").forbid_localhost("B").check(lambda: True, "C")
        assert result is v

    def test_multiple_errors(self):
        os.environ.pop("_TEST_MISS_A", None)
        os.environ["_TEST_LOCAL_B"] = "http://localhost:5000"
        v = ProductionValidator()
        v.require("_TEST_MISS_A").forbid_localhost("_TEST_LOCAL_B").check(lambda: False, "bad")
        errors = v.validate(environment="production")
        assert len(errors) == 3
        os.environ.pop("_TEST_LOCAL_B", None)

    def test_validate_prod_alias(self):
        os.environ.pop("_TEST_MISS", None)
        v = ProductionValidator()
        v.require("_TEST_MISS")
        errors = v.validate(environment="prod")
        assert len(errors) == 1