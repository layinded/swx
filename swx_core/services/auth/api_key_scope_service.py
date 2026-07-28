from typing import Optional
from uuid import UUID

from swx_core.models.api_key_scope import ApiKeyScopePublic


def validate_scope_format(resource: str, action: str) -> bool:
    return bool(resource and action and len(resource) <= 50 and len(action) <= 50)


async def check_permission(scopes: list[ApiKeyScopePublic], resource: str, action: str) -> bool:
    for scope in scopes:
        if scope.resource in (resource, "*") and scope.action in (action, "*"):
            return True
    return False


def expand_scopes(scopes: list[ApiKeyScopePublic]) -> list[str]:
    result: list[str] = []
    for scope in scopes:
        if scope.action == "*":
            result.append(f"{scope.resource}:*")
        else:
            result.append(f"{scope.resource}:{scope.action}")
    return result