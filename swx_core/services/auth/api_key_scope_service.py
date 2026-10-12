from swx_core.models.api_key_scope import ApiKeyScopePublic


def validate_scope_format(resource: str, action: str) -> bool:
    return bool(resource and action and len(resource) <= 50 and len(action) <= 50)


def parse_scope_string(scope: str) -> tuple[str, str]:
    """Parse 'resource:action' string into (resource, action) tuple.

    Inverse of expand_scopes().

    Raises:
        ValueError: If scope does not contain ':' separator
    """
    if ":" not in scope:
        raise ValueError(f"Invalid scope: {scope}. Expected 'resource:action'")
    resource, action = scope.split(":", 1)
    return resource, action


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