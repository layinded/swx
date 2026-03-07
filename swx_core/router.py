"""
SwX Router Module.

Handles dynamic route loading from both core and app directories.
Uses configurable discovery for app paths.
"""
import sys
import warnings
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends

from swx_core.config.settings import settings
from swx_core.utils.loader import dynamic_import, load_all_modules
from swx_core.config.discovery import discovery

# Force UTF-8 encoding for Windows (fix Unicode errors)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Initialize the main API router
router = APIRouter()


def router_module(
        module, full_module_name: str, main_router: APIRouter, version: Optional[str] = None
):
    """
    Dynamically registers a module's router.

    - If a user-defined prefix is set on the router, that prefix is used (prepended with the global prefix).
    - If no prefix is set, a default prefix is generated from the folder structure.
    - Also normalizes route paths to avoid duplicate segments.
    """
    if not hasattr(module, "router"):
        print(
            f"⚠️ WARNING: Module '{full_module_name}' does not have a 'router' attribute."
        )
        return

    # Split module path into parts (expecting structure like swx_core/routes/<folder>/<file>)
    module_parts = full_module_name.split(".")
    try:
        idx = module_parts.index("routes")
        route_parts = module_parts[idx + 1:]
    except ValueError:
        print(
            f"⚠️ WARNING: Could not determine route structure for '{full_module_name}'"
        )
        return

    if not route_parts:
        print(f"⚠️ WARNING: No route parts found for module '{full_module_name}'")
        return

    # Get the user-defined prefix from the router (if any)
    user_defined_prefix = getattr(module.router, "prefix", "").strip()

    # If no prefix is provided, generate a default one from the folder structure
    if not user_defined_prefix:
        subfolders = route_parts[:-1]
        route_file = route_parts[-1].replace("_route", "").replace("_routes", "")
        if subfolders and subfolders[-1].lower() == route_file.lower():
            default_prefix = "/" + "/".join(subfolders)
        else:
            default_prefix = "/" + "/".join(subfolders + [route_file])
        user_defined_prefix = default_prefix
        print(
            f"⚠️ No prefix set in {full_module_name}. Using default prefix: {user_defined_prefix}"
        )

    # Ensure the prefix starts with "/"
    if not user_defined_prefix.startswith("/"):
        user_defined_prefix = "/" + user_defined_prefix

    # Normalize each route's path: remove duplicate prefix if the route decorator includes it.
    normalized_prefix = user_defined_prefix.rstrip("/")
    for route in module.router.routes:
        if route.path.startswith(normalized_prefix):
            new_path = route.path[len(normalized_prefix):]
            if not new_path.startswith("/"):
                new_path = "/" + new_path
            # Avoid empty paths (default to "/")
            route.path = new_path or "/"

    # Clear the router's own prefix to prevent FastAPI from appending it again.
    module.router.prefix = ""

    # Prepend the global API prefix (e.g. "/api") to the user-defined/default prefix.
    include_prefix = f"{settings.ROUTE_PREFIX.rstrip('/')}{user_defined_prefix}"

    # NOTE: Admin route protection is now explicit.
    # Admin routes must use AdminUserDep dependency explicitly.
    # Implicit protection based on path name has been removed for security.
    # If you see this message, ensure your admin routes use:
    #   from swx_core.auth.admin.dependencies import AdminUserDep
    #   @router.get("/admin/...", dependencies=[Depends(AdminUserDep)])

    # Create a tag for OpenAPI docs based on the final prefix.
    tag_parts = [part.capitalize() for part in include_prefix.split("/") if part]
    if full_module_name.startswith("swx_core"):
        tag_prefix = "Core API"
    else:
        tag_prefix = "User API"

    tag = f"{tag_prefix} - {' - '.join(tag_parts)}"

    try:
        main_router.include_router(module.router, prefix=include_prefix, tags=[tag])
        print(
            f"✅ Registered route: '{full_module_name}' → '{include_prefix}' with tag '{tag}'"
        )
    except Exception as e:
        print(f"❌ ERROR: Failed to register router from '{full_module_name}': {e}")


# ------------------------------------------------------------------------------
# Dynamically load Core Routes from swx_core/routes
# ------------------------------------------------------------------------------
core_routes_dict = dynamic_import(
    "swx_core/routes", "swx_core.routes", recursive=True
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
    """
    # Check if app exists first
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
        router_module(module, full_module_name, router)


# ------------------------------------------------------------------------------
# Execute the Route Loaders
# ------------------------------------------------------------------------------
load_versioned_routes(router)
load_user_routes(router)

# Finally, load Core & User Models, Services, Repositories
load_all_modules()