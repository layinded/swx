"""
Registration Hook Registry
--------------------------
Allows apps to register pre/post registration hooks that are automatically
called by the auth route endpoint. Hooks are registered at app startup
and applied to every registration request.

Usage:
    from swx_core.core.hooks import registration_hooks

    # Register hooks at app startup
    registration_hooks.set_pre_register(my_validation_hook)
    registration_hooks.set_post_register(my_setup_hook)

    async def my_validation_hook(user_in: UserCreate, context: dict) -> UserCreate:
        user_in.tenant_id = context.get("tenant_id")
        return user_in

    async def my_setup_hook(user: User, context: dict) -> User:
        await create_organization(user.id, context.get("org_name"))
        return user
"""

from typing import Callable, Awaitable, Any
from swx_core.models.user import User, UserCreate

PreRegisterHook = Callable[[UserCreate, dict[str, Any]], Awaitable[UserCreate]]
PostRegisterHook = Callable[[User, dict[str, Any]], Awaitable[User | None]]


class RegistrationHookRegistry:
    __slots__ = ("_pre_hook", "_post_hook")

    def __init__(self):
        self._pre_hook: PreRegisterHook | None = None
        self._post_hook: PostRegisterHook | None = None

    def set_pre_register(self, hook: PreRegisterHook) -> None:
        self._pre_hook = hook

    def set_post_register(self, hook: PostRegisterHook) -> None:
        self._post_hook = hook

    @property
    def pre_register(self) -> PreRegisterHook | None:
        return self._pre_hook

    @property
    def post_register(self) -> PostRegisterHook | None:
        return self._post_hook

    def clear(self) -> None:
        self._pre_hook = None
        self._post_hook = None


registration_hooks = RegistrationHookRegistry()