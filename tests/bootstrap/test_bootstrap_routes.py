"""
Tests for bootstrap route registration, focusing on FastAPI 0.115.0+
_IncludedRouter compatibility.

Regression coverage for:
- v2.7.19: bootstrap_app crash (AttributeError: '_IncludedRouter' has no 'path')
- v2.7.20: routes silently not mounted (empty core_paths -> include_router skipped)
"""
import pytest
from fastapi import FastAPI, APIRouter

from swx_core.bootstrap import _extract_route_paths, bootstrap_app
from swx_core.router import router as core_router


def _app_route_paths(app: FastAPI) -> set[str]:
    return _extract_route_paths(app)


class TestExtractRoutePaths:

    def test_plain_routes(self):
        router = APIRouter()

        @router.get("/health")
        def health():
            return {"status": "ok"}

        @router.get("/users/{user_id}")
        def get_user(user_id: str):
            return {"id": user_id}

        paths = _extract_route_paths(router)
        assert "/health" in paths
        assert "/users/{user_id}" in paths

    def test_nested_included_router(self):
        """FastAPI 0.115.0+ wraps sub-routers in _IncludedRouter objects."""
        sub = APIRouter()

        @sub.get("/inner")
        def inner():
            return {}

        parent = APIRouter()
        parent.include_router(sub)

        @parent.get("/outer")
        def outer():
            return {}

        paths = _extract_route_paths(parent)

        assert "/inner" in paths, (
            "_IncludedRouter paths must be extracted recursively; "
            "if missing, _extract_route_paths is skipping wrapped routes"
        )
        assert "/outer" in paths

    def test_deeply_nested_routers(self):
        leaf = APIRouter()

        @leaf.get("/deep")
        def deep():
            return {}

        mid = APIRouter()
        mid.include_router(leaf)

        top = APIRouter()
        top.include_router(mid)

        paths = _extract_route_paths(top)
        assert "/deep" in paths

    def test_empty_router(self):
        router = APIRouter()
        assert _extract_route_paths(router) == set()

    def test_fastapi_app_with_included_subrouters(self):
        app = FastAPI()
        sub = APIRouter(prefix="/api/v1/widgets")

        @sub.get("/")
        def list_widgets():
            return []

        @sub.get("/{widget_id}")
        def get_widget(widget_id: str):
            return {"id": widget_id}

        app.include_router(sub)

        paths = _extract_route_paths(app)
        assert any("widgets" in p for p in paths), (
            f"Expected widget paths in {paths}; _IncludedRouter wrappers may be skipped"
        )


class TestBootstrapRouteRegistration:

    def test_core_routes_mounted_on_fresh_app(self):
        """The v2.7.20 regression: core routes silently not mounted."""
        app = FastAPI()

        before = _app_route_paths(app)
        bootstrap_app(app)
        after = _app_route_paths(app)

        assert len(after) > len(before), (
            "bootstrap_app must mount core routes on a fresh app; "
            "if after == before, include_router was skipped due to empty core_paths"
        )

    def test_core_routes_not_double_registered(self):
        app = FastAPI()
        bootstrap_app(app)
        paths_after_first = _app_route_paths(app)

        bootstrap_app(app)
        paths_after_second = _app_route_paths(app)

        assert paths_after_first == paths_after_second, (
            "Second bootstrap_app call should not add duplicate routes"
        )

    def test_core_router_has_real_paths(self):
        """Sanity: core_router must have actual routes, not just _IncludedRouter wrappers."""
        paths = _extract_route_paths(core_router)
        assert len(paths) > 0, (
            "core_router yielded zero paths; _extract_route_paths may be broken"
        )
