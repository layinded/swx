# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

import hashlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.content_filter import ContentFilter
from swx_core.models.safety_check import SafetyCheck, SafetyCheckCreate, SafetyCheckPublic
from swx_core.repositories import conversation_repository
from swx_core.repositories import safety_repository
from swx_core.services.safety.safety_cache import get_cached_filters


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _preview(content: str) -> str:
    return f"length={len(content)} sha256={_content_hash(content)[:16]}"


def _regex_flags(raw_flags: str | None) -> int:
    flags = 0
    for value in raw_flags or "":
        flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}.get(value, 0)
    return flags


def _match_filter(content_filter: ContentFilter, content: str) -> dict[str, Any]:
    config = content_filter.config or {}
    result: dict[str, Any] = {"filter_id": str(content_filter.id), "name": content_filter.name, "matched": False, "severity": content_filter.severity, "action": content_filter.action, "category": content_filter.category}
    if content_filter.filter_type == "regex" and config.get("pattern"):
        match = re.search(str(config["pattern"]), content, flags=_regex_flags(config.get("flags")))
        if match:
            result.update({"matched": True, "match_length": len(match.group(0)), "_replace_text": match.group(0)})
        return result
    keywords = [str(item) for item in config.get("keywords", []) if str(item).strip()]
    if not keywords and config.get("pattern"):
        keywords = [str(config["pattern"])]
    normalized_content = content if config.get("case_sensitive") else content.lower()
    matches = []
    for keyword in keywords:
        candidate = keyword if config.get("case_sensitive") else keyword.lower()
        if candidate and candidate in normalized_content:
            matches.append(keyword)
    if matches:
        result.update({"matched": True, "match_count": len(matches), "_replace_values": matches[:20]})
    return result


def _sanitize_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in result.items() if not key.startswith("_")} for result in results]


def _resolve_outcome(results: list[dict[str, Any]], content: str) -> tuple[str, str, dict[str, Any] | None]:
    matched = [result for result in results if result.get("matched")]
    if not matched:
        return "safe", "none", {"checked_filter_count": len(results)}
    blocked = next((result for result in matched if result.get("action") == "block"), None)
    if blocked is not None:
        return "blocked", "blocked", {"matched_filters": matched, "checked_filter_count": len(results)}
    replace_filters = [result for result in matched if result.get("action") == "replace"]
    if replace_filters:
        replacement = "[filtered]"
        for result in replace_filters:
            for value in result.get("_replace_values", []):
                content = content.replace(value, replacement)
            if result.get("_replace_text"):
                content = content.replace(str(result["_replace_text"]), replacement)
        return "flagged", "replaced", {"matched_filters": [str(result["filter_id"]) for result in matched], "replacement_applied": True, "checked_filter_count": len(results)}
    return "flagged", "flagged", {"matched_filters": [str(result["filter_id"]) for result in matched], "checked_filter_count": len(results)}


async def _validate_conversation_access(session: AsyncSession, conversation_id: UUID | None, user_id: UUID) -> None:
    if conversation_id is None:
        return
    conversation = await conversation_repository.get_conversation_by_id(session, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    if conversation.user_id != user_id:
        raise PermissionError("Conversation access denied")


async def _get_check_or_raise(session: AsyncSession, check_id: UUID, user_id: UUID | None = None) -> SafetyCheck:
    safety_check = await safety_repository.get_check_by_id(session, check_id)
    if safety_check is None:
        raise ValueError("Safety check not found")
    if user_id is not None and safety_check.user_id != user_id:
        raise PermissionError("Safety check access denied")
    return safety_check


async def run_safety_check(session: AsyncSession, content: str, content_type: str, user_id: UUID, source: str, conversation_id: UUID | None = None) -> SafetyCheckPublic:
    await _validate_conversation_access(session, conversation_id, user_id)
    filters = await get_cached_filters(session)
    filter_results = [_match_filter(content_filter, content) for content_filter in filters]
    public_filter_results = _sanitize_results(filter_results)
    overall_verdict, action_taken, metadata_ = _resolve_outcome(filter_results, content)
    payload = SafetyCheckCreate(content_type=content_type, content_hash=_content_hash(content), content_preview=_preview(content), source=source, user_id=user_id, conversation_id=conversation_id, filter_results={"results": public_filter_results}, overall_verdict=overall_verdict, action_taken=action_taken, metadata_=metadata_)
    safety_check = await safety_repository.create_check(session, payload.model_dump(exclude_unset=True))
    await event_bus.dispatch("safety.check_completed", payload={"check_id": str(safety_check.id), "user_id": str(user_id), "overall_verdict": overall_verdict, "action_taken": action_taken})
    return SafetyCheckPublic.model_validate(safety_check)


async def get_check(session: AsyncSession, check_id: UUID, user_id: UUID | None = None) -> SafetyCheckPublic:
    return SafetyCheckPublic.model_validate(await _get_check_or_raise(session, check_id, user_id))


async def list_checks(session: AsyncSession, user_id: UUID | None = None, overall_verdict: str | None = None, skip: int = 0, limit: int = 100) -> list[SafetyCheckPublic]:
    if user_id is not None and overall_verdict is None:
        checks = await safety_repository.list_checks_by_user(session, user_id, skip=skip, limit=limit)
    elif overall_verdict is not None and user_id is None:
        checks = await safety_repository.list_checks_by_verdict(session, overall_verdict, skip=skip, limit=limit)
    else:
        checks = await safety_repository.list_checks(session, user_id=user_id, overall_verdict=overall_verdict, skip=skip, limit=limit)
    return [SafetyCheckPublic.model_validate(check) for check in checks]
