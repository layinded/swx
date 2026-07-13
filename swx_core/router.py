"""
SwX Router Module.

Handles dynamic route loading from both core and app directories.
Uses configurable discovery for app paths.
"""

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


def router_module(
    module, full_module_name: str, main_router: APIRouter, version: Optional[str] = None
):
    """
    Dynamically registers a module's router.

    - If a user-defined prefix is set on the router, that prefix is used (prepended with the global prefix).
    - If no prefix is set, a default prefix is generated from the folder structure.
    - For versioned routes, the version segment is stripped from the prefix to avoid duplication.
    - Supports ROUTE_PREFIX module attribute to explicitly control prefix (use "/" for root-level).
    - Also normalizes route paths to avoid duplicate segments.
    """
    if not hasattr(module, "router"):
        msg = f"⚠️ WARNING: Module '{full_module_name}' does not have a 'router' attribute."
        if settings.STRICT_ROUTE_LOADING:
            raise ValueError(msg)
        print(msg)
        return

    # Split module path into parts (expecting structure like swx_core/routes/<folder>/<file>)
    module_parts = full_module_name.split(".")
    try:
        idx = module_parts.index("routes")
        route_parts = module_parts[idx + 1 :]
    except ValueError:
        print(
            f"⚠️ WARNING: Could not determine route structure for '{full_module_name}'"
        )
        return

    if not route_parts:
        print(f"⚠️ WARNING: No route parts found for module '{full_module_name}'")
        return

    # Build the version prefix for include_router (NOT including user_defined_prefix)
    # FastAPI will compose: include_prefix + router.prefix + route.path
    if version:
        include_prefix = f"{settings.ROUTE_PREFIX.rstrip('/')}/{version}"
    elif settings.CORE_ROUTE_PREFIX:
        core_prefix = settings.CORE_ROUTE_PREFIX.strip('/')
        include_prefix = f"{settings.ROUTE_PREFIX.rstrip('/')}/{core_prefix}"
    else:
        include_prefix = settings.ROUTE_PREFIX.rstrip('/')

    # Determine prefix: check module-level ROUTE_PREFIX first, then router.prefix
    route_prefix = getattr(module, "ROUTE_PREFIX", None)
    if route_prefix is not None:
        user_defined_prefix = route_prefix.strip()
    else:
        user_defined_prefix = getattr(module.router, "prefix", "").strip()

    # If no prefix is provided, generate a default one from the folder structure
    if not user_defined_prefix:
        subfolders = route_parts[:-1]
        route_file = route_parts[-1].replace("_route", "").replace("_routes", "")

        # For versioned routes, strip the version segment since it's already in include_prefix
        prefix_parts = list(subfolders)
        if version and prefix_parts[:1] == [version]:
            prefix_parts = prefix_parts[1:]

        prefix_tail = (
            prefix_parts
            if prefix_parts and prefix_parts[-1].lower() == route_file.lower()
            else prefix_parts + [route_file]
        )
        default_prefix = "/" + "/".join(prefix_tail)
        user_defined_prefix = default_prefix
        print(
            f"⚠️ No prefix set in {full_module_name}. Using default prefix: {user_defined_prefix}"
        )

    # Ensure the prefix starts with "/"
    if not user_defined_prefix.startswith("/"):
        user_defined_prefix = "/" + user_defined_prefix

    # For versioned routes, strip /api/{version} prefix from user_defined_prefix
    # to prevent doubling (e.g., /api/v1/api/v1/auth → /api/v1/auth)
    if version:
        version_prefix = f"/api/{version}"
        if user_defined_prefix.startswith(version_prefix):
            user_defined_prefix = user_defined_prefix[len(version_prefix):]

    # Set the user-defined prefix on the router (FastAPI will compose it with include_prefix)
    module.router.prefix = user_defined_prefix

    # Create a tag for OpenAPI docs based on the final prefix.
    # The actual path will be: include_prefix + user_defined_prefix
    full_path = f"{include_prefix}{user_defined_prefix}"
    tag_parts = [part.capitalize() for part in full_path.split("/") if part]
    tag_prefix = "Core API" if full_module_name.startswith("swx_core") else "User API"

    tag = f"{tag_prefix} - {' - '.join(tag_parts)}"

    try:
        # FastAPI composes: include_prefix + router.prefix + route.path
        main_router.include_router(module.router, prefix=include_prefix, tags=[tag])
        print(
            f"✅ Registered route: '{full_module_name}' → '{full_path}' with tag '{tag}'"
        )
    except Exception as e:
        print(f"❌ ERROR: Failed to register router from '{full_module_name}': {e}")


# ------------------------------------------------------------------------------
# Dynamically load Core Routes from swx_core/routes
# ------------------------------------------------------------------------------
import os

swx_path = os.path.dirname(os.path.abspath(__file__))
core_routes_dict = dynamic_import(
    os.path.join(swx_path, "routes"), "swx_core.routes", recursive=True
)
if core_routes_dict:
    for full_module_name, module in core_routes_dict.items():
        router_module(module, full_module_name, router)
else:
    print("⚠️ No core routes found in swx_core/routes.")


# ------------------------------------------------------------------------------
# Load Versioned Routes (e.g., v1, v2)
# ------------------------------------------------------------------------------
def load_versioned_routes(router: APIRouter):
    """
    Dynamically loads API routes from versioned folders (e.g., app/routes/v1, v2, etc.)
    and registers them under /api/v1/, /api/v2/, etc.

    Uses configurable discovery to find the app routes directory.
    """
    # Check if app exists first
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
        for full_module_name, module in api_routes_dict.items():
            router_module(module, full_module_name, router, version=version)

    if not versioned_routes_exist:
        print(
            "🔄 No versioned routes found! Only core and non-versioned routes will be available."
        )


# ------------------------------------------------------------------------------
# Load User Routes (Non-Versioned)
# ------------------------------------------------------------------------------
def load_user_routes(router: APIRouter):
    """
    Dynamically loads all non-versioned user-defined API routes from app/routes
    and registers them under the global route prefix.

    Uses configurable discovery to find the app routes directory.
    Skips versioned directories (v1, v2, etc.) to avoid duplicate registration.
    """
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

    for full_module_name, module in user_routes_dict.items():
        route_parts = full_module_name.split(".")

        if "routes" in route_parts:
            path_parts = route_parts[route_parts.index("routes") + 1 :]

            if path_parts and any(
                part.startswith("v") and len(part) > 1 and part[1:].isdigit()
                for part in path_parts
            ):
                print(
                    f"⏭️  Skipping versioned route: '{full_module_name}' (already loaded by load_versioned_routes)"
                )
                continue

        router_module(module, full_module_name, router)


# ------------------------------------------------------------------------------
# Execute the Route Loaders
# ------------------------------------------------------------------------------
load_versioned_routes(router)
load_user_routes(router)

# Finally, load Core & User Models, Services, Repositories
load_all_modules()
