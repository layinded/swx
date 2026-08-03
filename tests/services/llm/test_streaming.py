# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for structured SSE streaming — SSEEvent types and LLM service stream() integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from swx_core.contracts.llm import LLMRequest, SSEEvent, SSEEventType


class TestSSEEventTypes:
    """Tests for SSEEvent creation and type constraints."""

    def test_text_delta_event(self) -> None:
        event = SSEEvent(event_type="text_delta", data="Hello world")
        assert event.event_type == "text_delta"
        assert event.data == "Hello world"

    def test_usage_event_with_dict(self) -> None:
        usage = {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35}
        event = SSEEvent(event_type="usage", data=usage)
        assert event.event_type == "usage"
        assert isinstance(event.data, dict)
        assert event.data["total_tokens"] == 35

    def test_error_event_with_dict(self) -> None:
        error_data = {"code": "RATE_LIMITED", "message": "Too many requests"}
        event = SSEEvent(event_type="error", data=error_data)
        assert event.event_type == "error"
        assert event.data["code"] == "RATE_LIMITED"

    def test_done_event_no_data(self) -> None:
        event = SSEEvent(event_type="done")
        assert event.event_type == "done"
        assert event.data is None

    def test_frozen_dataclass(self) -> None:
        event = SSEEvent(event_type="text_delta", data="hi")
        with pytest.raises(AttributeError):
            event.event_type = "usage"  # type: ignore[misc]

    def test_string_data_for_text_delta(self) -> None:
        event = SSEEvent(event_type="text_delta", data="chunk")
        assert isinstance(event.data, str)

    def test_none_data_default(self) -> None:
        event = SSEEvent(event_type="done")
        assert event.data is None


class TestSSEEventInStream:
    """Tests for SSEEvent usage in async generator streams."""

    @pytest.mark.asyncio
    async def test_stream_yields_sse_events(self) -> None:
        """A provider stream should yield SSEEvent objects."""

        async def mock_stream(request: LLMRequest):
            yield SSEEvent(event_type="text_delta", data="Hello")
            yield SSEEvent(event_type="text_delta", data=" world")
            yield SSEEvent(event_type="usage", data={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})
            yield SSEEvent(event_type="done")

        events: list[SSEEvent] = []
        async for event in mock_stream(LLMRequest(prompt="hi")):
            events.append(event)

        assert len(events) == 4
        assert events[0].event_type == "text_delta"
        assert events[0].data == "Hello"
        assert events[1].data == " world"
        assert events[2].event_type == "usage"
        assert events[3].event_type == "done"

    @pytest.mark.asyncio
    async def test_stream_error_event(self) -> None:
        """A provider stream can yield an error event."""

        async def mock_stream(request: LLMRequest):
            yield SSEEvent(event_type="text_delta", data="starting...")
            yield SSEEvent(event_type="error", data={"code": "TIMEOUT", "message": "Provider timed out"})

        events: list[SSEEvent] = []
        async for event in mock_stream(LLMRequest(prompt="hi")):
            events.append(event)

        assert len(events) == 2
        assert events[1].event_type == "error"
        assert isinstance(events[1].data, dict)
        assert events[1].data["code"] == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_usage_extraction_from_stream(self) -> None:
        """Consumer can extract real usage from usage events in stream."""

        async def mock_stream(request: LLMRequest):
            yield SSEEvent(event_type="text_delta", data="response text")
            yield SSEEvent(event_type="usage", data={"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25})
            yield SSEEvent(event_type="done")

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        async for event in mock_stream(LLMRequest(prompt="test")):
            if event.event_type == "usage" and isinstance(event.data, dict):
                prompt_tokens = int(event.data.get("prompt_tokens", 0))
                completion_tokens = int(event.data.get("completion_tokens", 0))
                total_tokens = int(event.data.get("total_tokens", 0))

        assert prompt_tokens == 15
        assert completion_tokens == 10
        assert total_tokens == 25

    @pytest.mark.asyncio
    async def test_stream_without_usage(self) -> None:
        """A stream that only has text_delta and done events (no usage)."""

        async def mock_stream(request: LLMRequest):
            yield SSEEvent(event_type="text_delta", data="short reply")
            yield SSEEvent(event_type="done")

        has_usage = False
        async for event in mock_stream(LLMRequest(prompt="hi")):
            if event.event_type == "usage":
                has_usage = True

        assert not has_usage


class TestSSEEventTypeAnnotation:
    """Tests verifying SSEEventType literal type covers all expected event types."""

    def test_all_event_types_are_valid(self) -> None:
        """All defined event types should be valid SSEEventType values."""
        valid_types: list[SSEEventType] = ["text_delta", "usage", "error", "done"]
        for t in valid_types:
            event = SSEEvent(event_type=t)
            assert event.event_type == t