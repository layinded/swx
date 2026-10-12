"""Unit tests for usage metering cost calculation (pure function, no DB)."""

import pytest

from swx_core.config.settings import settings
from swx_core.services.billing.usage_metering_service import (
    UsageMeteringService,
    calculate_cost_nano,
)


class TestCalculateCostNano:
    def test_known_model_gpt4(self):
        pricing = settings.USAGE_METERING_MODEL_PRICING["gpt-4"]
        cost = calculate_cost_nano(input_tokens=1000, output_tokens=500, model_key="gpt-4")
        expected = 1000 * pricing["input"] + 500 * pricing["output"]
        assert cost == expected

    def test_known_model_claude3_haiku(self):
        pricing = settings.USAGE_METERING_MODEL_PRICING["claude-3-haiku"]
        cost = calculate_cost_nano(input_tokens=1000, output_tokens=500, model_key="claude-3-haiku")
        expected = 1000 * pricing["input"] + 500 * pricing["output"]
        assert cost == expected

    def test_unknown_model_uses_default(self):
        pricing = settings.USAGE_METERING_MODEL_PRICING["default"]
        cost = calculate_cost_nano(input_tokens=100, output_tokens=50, model_key="unknown-model")
        expected = 100 * pricing["input"] + 50 * pricing["output"]
        assert cost == expected

    def test_zero_tokens(self):
        assert calculate_cost_nano(0, 0, "gpt-4") == 0

    def test_only_input_tokens(self):
        pricing = settings.USAGE_METERING_MODEL_PRICING["gpt-3.5-turbo"]
        cost = calculate_cost_nano(1000, 0, "gpt-3.5-turbo")
        assert cost == 1000 * pricing["input"]

    def test_only_output_tokens(self):
        pricing = settings.USAGE_METERING_MODEL_PRICING["gpt-3.5-turbo"]
        cost = calculate_cost_nano(0, 1000, "gpt-3.5-turbo")
        assert cost == 1000 * pricing["output"]

    def test_all_models_have_pricing(self):
        required = {"gpt-4", "gpt-4o", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "default"}
        assert required.issubset(set(settings.USAGE_METERING_MODEL_PRICING.keys()))

    def test_all_pricing_positive(self):
        for model, pricing in settings.USAGE_METERING_MODEL_PRICING.items():
            assert pricing["input"] > 0, f"{model} input price not positive"
            assert pricing["output"] > 0, f"{model} output price not positive"

    def test_output_more_expensive_than_input(self):
        for model, pricing in settings.USAGE_METERING_MODEL_PRICING.items():
            assert pricing["output"] >= pricing["input"], f"{model} output should be >= input"


class TestUsageMeteringServiceInit:
    def test_service_requires_session(self):
        with pytest.raises(TypeError):
            UsageMeteringService()  # type: ignore[call-arg]