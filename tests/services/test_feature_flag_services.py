# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.feature_flag import FeatureFlagCreate, FeatureFlagUpdate
from swx_core.models.flag_evaluation import FlagEvaluationCreate
from swx_core.services.feature_flag import feature_flag_service, feature_flag_evaluation_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def flag_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "key": "dark-mode",
        "name": "Dark Mode",
        "description": "Enable dark mode UI",
        "enabled": True,
        "default_value": None,
        "rules": None,
        "variants": None,
        "sticky": False,
        "start_date": None,
        "end_date": None,
        "metadata_": None,
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def evaluation_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "flag_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "variant": None,
        "value": None,
        "reason": "enabled",
        "context": None,
        "created_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


class TestFeatureFlagService:
    async def test_create_flag_emits_event(self):
        session = AsyncMock()
        body = FeatureFlagCreate(key="dark-mode", name="Dark Mode", description="Enable dark mode")
        stored = flag_object()
        with patch.object(feature_flag_service.feature_flag_repository, "create_flag", new_callable=AsyncMock, return_value=stored):
            with patch.object(feature_flag_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await feature_flag_service.create_flag(session, body)
        assert result.key == "dark-mode"
        assert mock_dispatch.await_args.args[0] == "feature_flag.created"

    async def test_get_flag_raises_for_missing(self):
        session = AsyncMock()
        flag_id = uuid.uuid4()
        with patch.object(feature_flag_service.feature_flag_repository, "get_flag_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await feature_flag_service.get_flag(session, flag_id)

    async def test_get_flag_by_key_raises_for_missing(self):
        session = AsyncMock()
        with patch.object(feature_flag_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await feature_flag_service.get_flag_by_key(session, "nonexistent")

    async def test_update_flag_emits_event(self):
        session = AsyncMock()
        flag_id = uuid.uuid4()
        stored = flag_object(id=flag_id)
        updated = flag_object(id=flag_id, description="Updated description")
        body = FeatureFlagUpdate(description="Updated description")
        with patch.object(feature_flag_service.feature_flag_repository, "get_flag_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(feature_flag_service.feature_flag_repository, "update_flag", new_callable=AsyncMock, return_value=updated):
                with patch.object(feature_flag_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await feature_flag_service.update_flag(session, flag_id, body)
        assert result.description == "Updated description"
        assert mock_dispatch.await_args.args[0] == "feature_flag.updated"

    async def test_delete_flag_emits_event(self):
        session = AsyncMock()
        flag_id = uuid.uuid4()
        stored = flag_object(id=flag_id)
        with patch.object(feature_flag_service.feature_flag_repository, "get_flag_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(feature_flag_service.feature_flag_repository, "delete_flag", new_callable=AsyncMock, return_value=stored):
                with patch.object(feature_flag_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await feature_flag_service.delete_flag(session, flag_id)
        assert mock_dispatch.await_args.args[0] == "feature_flag.deleted"


class TestFeatureFlagEvaluation:
    async def test_evaluate_flag_returns_not_found_for_missing_key(self):
        session = AsyncMock()
        with patch.object(feature_flag_evaluation_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=None):
            result = await feature_flag_evaluation_service.evaluate_flag(session, "nonexistent")
        assert result["enabled"] is False
        assert result["reason"] == "not_found"

    async def test_evaluate_flag_returns_disabled_for_disabled_flag(self):
        session = AsyncMock()
        flag = flag_object(enabled=False, default_value=None)
        with patch.object(feature_flag_evaluation_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=flag):
            result = await feature_flag_evaluation_service.evaluate_flag(session, "dark-mode")
        assert result["enabled"] is False
        assert result["reason"] == "disabled"

    async def test_evaluate_flag_returns_enabled_for_enabled_flag(self):
        session = AsyncMock()
        flag = flag_object(enabled=True, default_value=None)
        eval_obj = evaluation_object(flag_id=flag.id, reason="enabled")
        with patch.object(feature_flag_evaluation_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=flag):
            with patch.object(feature_flag_evaluation_service.feature_flag_repository, "create_evaluation", new_callable=AsyncMock, return_value=eval_obj):
                with patch.object(feature_flag_evaluation_service.event_bus, "dispatch", new_callable=AsyncMock):
                    result = await feature_flag_evaluation_service.evaluate_flag(session, "dark-mode")
        assert result["enabled"] is True
        assert result["reason"] == "enabled"

    async def test_evaluate_flag_with_variant_assignment(self):
        session = AsyncMock()
        variants = {"options": [{"name": "control", "value": {"ui": "default"}, "weight": 1}, {"name": "variant_a", "value": {"ui": "new"}, "weight": 1}]}
        flag = flag_object(enabled=True, variants=variants, default_value=None)
        eval_obj = evaluation_object(flag_id=flag.id, variant="variant_a", value={"ui": "new"}, reason="variant_assigned")
        with patch.object(feature_flag_evaluation_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=flag):
            with patch.object(feature_flag_evaluation_service.feature_flag_repository, "create_evaluation", new_callable=AsyncMock, return_value=eval_obj):
                with patch.object(feature_flag_evaluation_service.event_bus, "dispatch", new_callable=AsyncMock):
                    result = await feature_flag_evaluation_service.evaluate_flag(session, "dark-mode", user_id=uuid.uuid4())
        assert result["enabled"] is True

    async def test_evaluate_flags_for_user(self):
        session = AsyncMock()
        flag = flag_object(enabled=True, key="dark-mode")
        eval_obj = evaluation_object(flag_id=flag.id)
        with patch.object(feature_flag_evaluation_service.feature_flag_repository, "list_flags", new_callable=AsyncMock, return_value=[flag]):
            with patch.object(feature_flag_evaluation_service.feature_flag_repository, "get_flag_by_key", new_callable=AsyncMock, return_value=flag):
                with patch.object(feature_flag_evaluation_service.feature_flag_repository, "create_evaluation", new_callable=AsyncMock, return_value=eval_obj):
                    with patch.object(feature_flag_evaluation_service.event_bus, "dispatch", new_callable=AsyncMock):
                        results = await feature_flag_evaluation_service.evaluate_flags_for_user(session)
        assert len(results) == 1
        assert results[0]["flag_key"] == "dark-mode"


class TestDetermineVariant:
    def test_determine_variant_with_variants_and_user(self):
        variants = {"options": [{"name": "control", "value": "default", "weight": 1}, {"name": "variant_a", "value": "new_ui", "weight": 1}]}
        variant, value = feature_flag_evaluation_service._determine_variant(variants, uuid.UUID("12345678-1234-5678-1234-567812345678"), "test-flag")
        assert variant is not None
        assert value is not None

    def test_determine_variant_with_no_variants(self):
        variant, value = feature_flag_evaluation_service._determine_variant(None, uuid.uuid4(), "test-flag")
        assert variant is None
        assert value is None

    def test_determine_variant_with_empty_options(self):
        variants = {"options": []}
        variant, value = feature_flag_evaluation_service._determine_variant(variants, uuid.uuid4(), "test-flag")
        assert variant is None
        assert value is None

    def test_determine_variant_with_no_user_returns_first(self):
        variants = {"options": [{"name": "control", "value": {"ui": "default"}, "weight": 1}]}
        variant, value = feature_flag_evaluation_service._determine_variant(variants, None, "test-flag")
        assert variant == "control"
        assert value == {"ui": "default"}