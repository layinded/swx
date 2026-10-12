"""
Registration Hook Registry
--------------------------
Allows apps to register pre/post registration hooks that are automatically
called by the auth route endpoint. Hooks are registered at app startup
and applied to every registration request.

Post-register hooks receive the parent database session so side effects
(create team, assign role, billing account) share the same transaction.
This avoids separate-session bugs like MissingGreenlet and lazy-load errors.

Usage:
    from swx_core.core.hooks import registration_hooks

    # Register hooks at app startup
    registration_hooks.set_pre_register(my_validation_hook)
    registration_hooks.set_post_register(my_setup_hook)

    async def my_validation_hook(user_in: UserCreate, context: dict) -> UserCreate:
        user_in.tenant_id = context.get("tenant_id")
        return user_in

    async def my_setup_hook(user: User, session: AsyncSession, context: dict) -> User:
        await create_organization(user.id, context.get("org_name"), session=session)
        return user
"""

from typing import Callable, Awaitable, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user import User, UserCreate

PreRegisterHook = Callable[[UserCreate, dict[str, Any]], Awaitable[UserCreate]]
PostRegisterHook = Callable[[User, AsyncSession, dict[str, Any]], Awaitable[User | None]]


class RegistrationHookRegistry:
    __slots__ = ("_pre_hook", "_post_hooks")

    def __init__(self):
        self._pre_hook: PreRegisterHook | None = None
        self._post_hooks: List[PostRegisterHook] = []

    def set_pre_register(self, hook: PreRegisterHook) -> None:
        self._pre_hook = hook

    def add_post_register(self, hook: PostRegisterHook) -> None:
        self._post_hooks.append(hook)

    def set_post_register(self, hook: PostRegisterHook) -> None:
        self._post_hooks = [hook]

    @property
    def pre_register(self) -> PreRegisterHook | None:
        return self._pre_hook

    @property
    def post_register(self) -> PostRegisterHook | None:
        if not self._post_hooks:
            return None

        hooks = list(self._post_hooks)

        async def combined_post_hook(user: User, session: AsyncSession, context: dict[str, Any]) -> User | None:
            result: User | None = user
            for h in hooks:
                try:
                    result = await h(user, session, context)
                except Exception:
                    from swx_core.middleware.logging_middleware import logger
                    logger.exception(f"Post-register hook {h.__name__} failed")
            return result

        combined_post_hook.__name__ = "combined_post_register_hook"
        return combined_post_hook

    def clear(self) -> None:
        self._pre_hook = None
        self._post_hooks = []


registration_hooks = RegistrationHookRegistry()