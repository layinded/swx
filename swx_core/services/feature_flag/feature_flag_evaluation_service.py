# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

import hashlib
from swx_core.utils.time import utc_now

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.flag_evaluation import FlagEvaluationCreate, FlagEvaluationPublic
from swx_core.repositories import feature_flag_repository

def _determine_variant(variants: dict[str, Any] | None, user_id: UUID | None, flag_key: str) -> tuple[str | None, dict[str, Any] | None]:
    if not variants:
        return None, None
    variant_list = variants.get("options", [])
    if not variant_list:
        return None, None
    if user_id is not None:
        hash_input = f"{flag_key}:{user_id}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        total_weight = sum(v.get("weight", 1) for v in variant_list)
        selected = hash_val % total_weight
        cumulative = 0
        for variant in variant_list:
            cumulative += variant.get("weight", 1)
            if selected < cumulative:
                return variant.get("name"), variant.get("value")
    first = variant_list[0]
    return first.get("name"), first.get("value")

async def evaluate_flag(session: AsyncSession, flag_key: str, user_id: UUID | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    flag = await feature_flag_repository.get_flag_by_key(session, flag_key)
    if flag is None:
        return {"flag_key": flag_key, "enabled": False, "variant": None, "value": None, "reason": "not_found"}
    now_utc = utc_now()
    if flag.start_date and now_utc < flag.start_date:
        result = {"flag_key": flag_key, "enabled": False, "variant": None, "value": flag.default_value, "reason": "not_started"}
    elif flag.end_date and now_utc > flag.end_date:
        result = {"flag_key": flag_key, "enabled": False, "variant": None, "value": flag.default_value, "reason": "expired"}
    elif not flag.enabled:
        result = {"flag_key": flag_key, "enabled": False, "variant": None, "value": flag.default_value, "reason": "disabled"}
    else:
        variant, value = _determine_variant(flag.variants, user_id, flag_key)
        reason = "variant_assigned" if variant else "enabled"
        result = {"flag_key": flag_key, "enabled": True, "variant": variant, "value": value or flag.default_value, "reason": reason}
    if flag.id is not None:
        evaluation_create = FlagEvaluationCreate(
            flag_id=flag.id,
            user_id=user_id,
            variant=result.get("variant"),
            value=result.get("value"),
            reason=result["reason"],
            context=context,
        )
        evaluation = await feature_flag_repository.create_evaluation(session, evaluation_create.model_dump(exclude_unset=True))
        await event_bus.dispatch("feature_flag.evaluated", payload={"flag_key": flag_key, "flag_id": str(flag.id), "reason": result["reason"]})
        result["evaluation_id"] = str(evaluation.id)
    return result

async def evaluate_flags_for_user(session: AsyncSession, user_id: UUID | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    enabled_flags = await feature_flag_repository.list_flags(session, enabled=True, skip=0, limit=200)
    results = []
    for flag in enabled_flags:
        result = await evaluate_flag(session, flag.key, user_id, context)
        results.append(result)
    return results

async def get_flag_evaluations(session: AsyncSession, flag_id: UUID, skip: int = 0, limit: int = 50) -> list[FlagEvaluationPublic]:
    evaluations = await feature_flag_repository.list_evaluations(session, flag_id=flag_id, skip=skip, limit=limit)
    return [FlagEvaluationPublic.model_validate(e) for e in evaluations]

async def get_user_evaluations(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50) -> list[FlagEvaluationPublic]:
    evaluations = await feature_flag_repository.list_evaluations(session, user_id=user_id, skip=skip, limit=limit)
    return [FlagEvaluationPublic.model_validate(e) for e in evaluations]