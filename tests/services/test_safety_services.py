# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.content_filter import ContentFilter, ContentFilterCreate, ContentFilterUpdate
from swx_core.models.safety_check import SafetyCheck, SafetyCheckCreate
from swx_core.services.safety import safety_service, safety_check_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def filter_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "profanity-filter",
        "description": "Filters profane words",
        "filter_type": "keyword",
        "config": {"keywords": ["badword"], "case_sensitive": False},
        "severity": "high",
        "action": "block",
        "enabled": True,
        "category": "content",
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def check_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "content_type": "input",
        "content_hash": "abc123def456",
        "content_preview": "length=5 sha256=abc123def456",
        "source": "direct",
        "user_id": uuid.uuid4(),
        "conversation_id": None,
        "filter_results": {"results": []},
        "overall_verdict": "safe",
        "action_taken": "none",
        "metadata_": None,
        "created_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data)


class TestSafetyFilterService:
    async def test_create_filter_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        body = ContentFilterCreate(name="profanity", filter_type="keyword", config={"keywords": ["bad"]})
        stored = filter_object()
        with patch.object(safety_service.safety_repository, "create_filter", new_callable=AsyncMock, return_value=stored):
            with patch.object(safety_service, "invalidate_cache") as mock_invalidate:
                with patch.object(safety_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await safety_service.create_filter(session, body)
        assert result.name == "profanity-filter"
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "safety.filter_created"

    async def test_update_filter_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        filter_id = uuid.uuid4()
        stored = filter_object(id=filter_id)
        updated = filter_object(id=filter_id, name="updated")
        body = ContentFilterUpdate(name="updated")
        with patch.object(safety_service.safety_repository, "get_filter_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(safety_service.safety_repository, "update_filter", new_callable=AsyncMock, return_value=updated):
                with patch.object(safety_service, "invalidate_cache") as mock_invalidate:
                    with patch.object(safety_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await safety_service.update_filter(session, filter_id, body)
        assert result.name == "updated"
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "safety.filter_updated"

    async def test_delete_filter_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        filter_id = uuid.uuid4()
        stored = filter_object(id=filter_id)
        with patch.object(safety_service.safety_repository, "get_filter_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(safety_service.safety_repository, "delete_filter", new_callable=AsyncMock, return_value=stored):
                with patch.object(safety_service, "invalidate_cache") as mock_invalidate:
                    with patch.object(safety_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await safety_service.delete_filter(session, filter_id)
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "safety.filter_deleted"

    async def test_get_filter_raises_for_missing(self):
        session = AsyncMock()
        filter_id = uuid.uuid4()
        with patch.object(safety_service.safety_repository, "get_filter_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await safety_service.get_filter(session, filter_id)


class TestSafetyCheckService:
    async def test_run_safety_check_safe_content(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        check = check_object(user_id=user_id, overall_verdict="safe", action_taken="none")
        with patch.object(safety_check_service, "get_cached_filters", new_callable=AsyncMock, return_value=[]):
            with patch.object(safety_check_service.safety_repository, "create_check", new_callable=AsyncMock, return_value=check):
                with patch.object(safety_check_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await safety_check_service.run_safety_check(session, "hello world", "input", user_id, "direct")
        assert mock_dispatch.await_args.args[0] == "safety.check_completed"

    async def test_run_safety_check_with_keyword_filter_match(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        content_filter = ContentFilter(id=uuid.uuid4(), name="profanity", filter_type="keyword", config={"keywords": ["badword"], "case_sensitive": False}, severity="high", action="block", enabled=True, category="content", created_at=now(), updated_at=now())
        check = check_object(user_id=user_id, overall_verdict="blocked", action_taken="blocked")
        with patch.object(safety_check_service, "get_cached_filters", new_callable=AsyncMock, return_value=[content_filter]):
            with patch.object(safety_check_service.safety_repository, "create_check", new_callable=AsyncMock, return_value=check):
                with patch.object(safety_check_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await safety_check_service.run_safety_check(session, "this has badword in it", "input", user_id, "direct")
        assert mock_dispatch.await_args.args[0] == "safety.check_completed"

    async def test_run_safety_check_with_regex_filter_match(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        content_filter = ContentFilter(id=uuid.uuid4(), name="email-filter", filter_type="regex", config={"pattern": r"\\b[\\w.-]+@[\\w.-]+\\.\\w+\\b", "flags": ""}, severity="medium", action="flag", enabled=True, category="pii", created_at=now(), updated_at=now())
        check = check_object(user_id=user_id, overall_verdict="flagged", action_taken="flagged")
        with patch.object(safety_check_service, "get_cached_filters", new_callable=AsyncMock, return_value=[content_filter]):
            with patch.object(safety_check_service.safety_repository, "create_check", new_callable=AsyncMock, return_value=check):
                with patch.object(safety_check_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await safety_check_service.run_safety_check(session, "contact user@example.com for info", "input", user_id, "direct")
        assert mock_dispatch.await_args is not None

    async def test_get_check_raises_for_missing(self):
        session = AsyncMock()
        check_id = uuid.uuid4()
        with patch.object(safety_check_service.safety_repository, "get_check_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await safety_check_service.get_check(session, check_id)

    async def test_get_check_raises_permission_error_for_wrong_user(self):
        session = AsyncMock()
        check_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        stored = check_object(id=check_id, user_id=owner_id)
        with patch.object(safety_check_service.safety_repository, "get_check_by_id", new_callable=AsyncMock, return_value=stored):
            with pytest.raises(PermissionError, match="access denied"):
                await safety_check_service.get_check(session, check_id, user_id=other_id)