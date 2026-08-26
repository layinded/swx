"""
SwX Router Module.

Handles dynamic route loading from both core and app directories.
Uses configurable discovery for app paths.
"""

import os
import sys
import warnings
from typing import Optional

from fastapi import APIRouter

from swx_core.config.settings import settings
from swx_core.utils.loader import dynamic_import, load_all_modules
from swx_core.config.discovery import discovery

# Force UTF-8 encoding for Windows (fix Unicode errors)
if sys.platform == "win32":
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

# Initialize the main API router
router = APIRouter()


def _register_router(
    module_router: APIRouter,
    module,
    full_module_name: str,
    main_router: APIRouter,
    include_prefix: str,
    version: Optional[str],
    route_parts: list[str],
    is_core: bool,
    ws: bool = False,
):
    """Register a single APIRouter (HTTP or WebSocket) onto main_router.

    Resolves the prefix from ``ROUTE_PREFIX`` module attr or the router's own
    ``.prefix``, falling back to a path derived from ``route_parts``.  Then
    calls ``main_router.include_router(...)`` with the composed prefix and tag.
    """
    module_prefix = getattr(module, "ROUTE_PREFIX", None)
    if module_prefix is not None:
        user_defined_prefix = module_prefix.strip()
    else:
        user_defined_prefix = module_router.prefix.strip()

    if not user_defined_prefix:
        subfolders = route_parts[:-1]
        route_file = route_parts[-1].replace("_route", "").replace("_routes", "")
        prefix_parts = list(subfolders)
        if version and prefix_parts[:1] == [version]:
            prefix_parts = prefix_parts[1:]
        prefix_tail = (
            prefix_parts
            if prefix_parts and prefix_parts[-1].lower() == route_file.lower()
            else prefix_parts + [route_file]
        )
        user_defined_prefix = "/" + "/".join(prefix_tail)

    if not user_defined_prefix.startswith("/"):
        user_defined_prefix = "/" + user_defined_prefix

    if version:
        version_prefix = f"/api/{version}"
        if user_defined_prefix.startswith(version_prefix):
            user_defined_prefix = user_defined_prefix[len(version_prefix):]

    module_router.prefix = user_defined_prefix
    full_path = f"{include_prefix}{user_defined_prefix}"
    tag_parts = [part.capitalize() for part in full_path.split("/") if part]
    tag_prefix = "Core API" if is_core else "User API"
    kind = "WS" if ws else "route"
    tag = f"{tag_prefix} - {' - '.join(tag_parts)}"

    try:
        main_router.include_router(module_router, prefix=include_prefix, tags=[tag])
        print(f"✅ Registered {kind}: '{full_module_name}' → '{full_path}' with tag '{tag}'")
    except Exception as e:
        print(f"❌ ERROR: Failed to register {kind} from '{full_module_name}': {e}")


def router_module(
    module, full_module_name: str, main_router: APIRouter, version: Optional[str] = None
):
    """Discover and mount HTTP and WebSocket routers from *module*.

    Looks for ``module.router`` (HTTP) and ``module.websocket_router``
    (WebSocket).  Both are optional — a module may expose either, both,
    or neither (which emits a warning).

    - ``module.router``: registered under the standard API prefix.
    - ``module.websocket_router``: registered under the same prefix so
      WebSocket endpoints live alongside their HTTP siblings.
    """
    module_parts = full_module_name.split(".")
    try:
        idx = module_parts.index("routes")
        route_parts = module_parts[idx + 1:]
    except ValueError:
        print(f"⚠️ WARNING: Could not determine route structure for '{full_module_name}'")
        return

    if not route_parts:
        print(f"⚠️ WARNING: No route parts found for module '{full_module_name}'")
        return

    if version:
        include_prefix = f"{settings.ROUTE_PREFIX.rstrip('/')}/{version}"
    elif settings.CORE_ROUTE_PREFIX:
        core_prefix = settings.CORE_ROUTE_PREFIX.strip('/')
        include_prefix = f"{settings.ROUTE_PREFIX.rstrip('/')}/{core_prefix}"
    else:
        include_prefix = settings.ROUTE_PREFIX.rstrip('/')

    is_core = full_module_name.startswith("swx_core")

    has_http = hasattr(module, "router")
    has_ws = hasattr(module, "websocket_router")

    if not has_http and not has_ws:
        msg = f"⚠️ WARNING: Module '{full_module_name}' has neither 'router' nor 'websocket_router'."
        if settings.STRICT_ROUTE_LOADING:
            raise ValueError(msg)
        print(msg)
        return

    if has_http:
        _register_router(
            module.router, module, full_module_name, main_router,
            include_prefix, version, route_parts, is_core, ws=False,
        )

    if has_ws:
        _register_router(
            module.websocket_router, module, full_module_name, main_router,
            include_prefix, version, route_parts, is_core, ws=True,
        )


def _dedup_aggregated_packages(
    routes_dict: dict[str, object],
) -> tuple[set[str], set[str]]:
    """Identify aggregated packages and their sub-modules to prevent duplicate endpoints.

    When a route **package** (``__init__.py``) exposes a ``router`` or
    ``websocket_router`` that aggregates sub-routers via ``include_router()``,
    registering each sub-module individually would duplicate endpoints.
    Only packages (modules with ``__path__``) are aggregators — leaf modules
    with ``router`` are independent route definitions, not aggregators.
    """
    aggregated: set[str] = set()
    skipped: set[str] = set()

    for mod_name, mod in routes_dict.items():
        is_package = hasattr(mod, "__path__")
        has_router = hasattr(mod, "router") or hasattr(mod, "websocket_router")
        if is_package and has_router:
            prefix = mod_name + "."
            for other in routes_dict:
                if other.startswith(prefix):
                    skipped.add(other)
            aggregated.add(mod_name)

    return aggregated, skipped


def _load_routes_dict(
    routes_dict: dict[str, object], main_router: APIRouter, version: Optional[str] = None
) -> None:
    """Load a routes dict, skipping sub-modules of aggregated packages."""
    aggregated, skipped = _dedup_aggregated_packages(routes_dict)
    for full_module_name, module in routes_dict.items():
        if full_module_name in skipped and full_module_name not in aggregated:
            print(f"⏭️  Skipping '{full_module_name}' (handled by aggregated package)")
            continue
        router_module(module, full_module_name, main_router, version=version)


# ------------------------------------------------------------------------------
# Dynamically load Core Routes from swx_core/routes
# ------------------------------------------------------------------------------

swx_path = os.path.dirname(os.path.abspath(__file__))
core_routes_dict = dynamic_import(
    os.path.join(swx_path, "routes"), "swx_core.routes", recursive=True
)
if core_routes_dict:
    _load_routes_dict(core_routes_dict, router)
else:
    print("⚠️ No core routes found in swx_core/routes.")


# ------------------------------------------------------------------------------
# Load Versioned Routes (e.g., v1, v2)
# ------------------------------------------------------------------------------
def load_versioned_routes(router: APIRouter):
    if not discovery.app_exists():
        print("⚠️ App directory not found. Skipping versioned routes.")
        return

    versioned_routes_exist = False
    for version in settings.API_VERSIONS:
        routes_path = discovery.app_routes_path / version
        if not routes_path.exists():
            print(f"⚠️ No routes found for `{version}`. Skipping...")
            continue

        api_routes_dict = dynamic_import(
            str(routes_path),
            f"{discovery.app_routes_module}.{version}",
            recursive=True,
        )
        if not api_routes_dict:
            warnings.warn(f"⚠️ No API routes found in `{routes_path}`.", stacklevel=2)
            continue

        versioned_routes_exist = True
        _load_routes_dict(api_routes_dict, router, version=version)

    if not versioned_routes_exist:
        print("🔄 No versioned routes found! Only core and non-versioned routes will be available.")


# ------------------------------------------------------------------------------
# Load User Routes (Non-Versioned)
# ------------------------------------------------------------------------------
def load_user_routes(router: APIRouter):
    if not discovery.app_exists():
        print("⚠️ App directory not found. Skipping user routes.")
        return

    routes_path = discovery.app_routes_path
    if not routes_path.exists():
        print("⚠️ No user-defined API routes found. Skipping...")
        return

    user_routes_dict = dynamic_import(
        str(routes_path), discovery.app_routes_module, recursive=True
    )
    if not user_routes_dict:
        warnings.warn(
            f"⚠️ No user-defined API routes found in `{routes_path}`.", stacklevel=2
        )
        return

    # Filter out versioned routes (already loaded by load_versioned_routes)
    filtered: dict[str, object] = {}
    for full_module_name, module in user_routes_dict.items():
        route_parts = full_module_name.split(".")
        if "routes" in route_parts:
            path_parts = route_parts[route_parts.index("routes") + 1:]
            if path_parts and any(
                part.startswith("v") and len(part) > 1 and part[1:].isdigit()
                for part in path_parts
            ):
                print(f"⏭️  Skipping versioned route: '{full_module_name}' (already loaded by load_versioned_routes)")
                continue
        filtered[full_module_name] = module

    _load_routes_dict(filtered, router)


# ------------------------------------------------------------------------------
# Execute the Route Loaders
# ------------------------------------------------------------------------------
load_versioned_routes(router)
load_user_routes(router)

load_all_modules()
