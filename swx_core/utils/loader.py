"""
Module Loader
-------------
This module dynamically loads and imports:
- Models, services, repositories, and middleware from both `swx_core/` and app directories.
- Middleware components that define an `apply_middleware(app: FastAPI)` function.

Features:
- Recursively imports all submodules in specified directories.
- Reloads already imported modules for real-time updates.
- Ensures middleware is loaded properly in FastAPI applications.
- Uses configurable discovery for app paths (no hardcoded swx_app).

Functions:
- `dynamic_import()`: Dynamically imports all modules within a specified path.
- `load_all_modules()`: Loads models, services, repositories, and middleware dynamically.
- `load_middleware()`: Loads and applies middleware to a FastAPI application.
"""

import importlib
import pkgutil
import sys
from pathlib import Path
import traceback
from typing import Dict, Any

from fastapi import FastAPI

from swx_core.middleware.logging_middleware import logger
from swx_core.middleware.session_middleware import setup_session_middleware
from swx_core.config.discovery import discovery


def dynamic_import(base_path: str, package_name: str, recursive: bool = False) -> Dict[str, Any]:
    """
    Dynamically imports all modules within the given `base_path` and associates them with the specified `package_name`.

    Args:
        base_path (str): The base directory path to search for modules.
        package_name (str): The package name associated with the base path.
        recursive (bool, optional): Whether to recursively import submodules. Defaults to False.

    Returns:
        Dict[str, Any]: A dictionary where keys are module names and values are imported modules.

    Behavior:
        - Ensures that modules are reloaded if already imported.
        - Supports recursive importing of submodules.
        - Handles OS-specific paths.
        - Logs errors for failed imports.
        - Returns empty dict if path doesn't exist.

    Example:
        `dynamic_import("my_app/models", "my_app.models")`
    """
    imported_modules = {}
    package_path = Path(base_path).resolve()  # Get absolute path

    if not package_path.exists():
        logger.debug(f"Path does not exist, skipping: {base_path}")
        return imported_modules

    for finder, mod_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
        full_module_name = f"{package_name}.{mod_name}"

        try:
            # Skip reload for model modules: re-execution re-registers tables and raises
            # "Table 'X' is already defined for this MetaData instance".
            skip_reload = ".models." in full_module_name

            if full_module_name in sys.modules:
                if not skip_reload:
                    importlib.reload(sys.modules[full_module_name])
                    logger.info(f"Reloaded module: {full_module_name}")
            else:
                module = importlib.import_module(full_module_name)
                sys.modules[full_module_name] = module
                logger.info(f"Loaded new module: {full_module_name}")

            # Store using full module name as key
            imported_modules[full_module_name] = sys.modules[full_module_name]

            # Recursive Import for Nested Folders
            if recursive and is_pkg:
                subdir_path = package_path / mod_name
                subpackage_name = full_module_name  # Keep full package path
                submodules = dynamic_import(str(subdir_path), subpackage_name, recursive=True)
                imported_modules.update(submodules)

        except Exception as e:
            logger.error(f"Error loading {full_module_name}: {e}\n{traceback.format_exc()}")

    return imported_modules


def load_all_modules() -> None:
    """
    Loads models, services, repositories, and middleware dynamically from both `swx_core/` and app directories.

    Uses configurable discovery to determine which app modules to load.
    If the app directory doesn't exist, only core modules are loaded.

    Logs:
        - Number of loaded modules from each package.

    Example:
        `load_all_modules()` -> Loads all components dynamically at startup.
    """
    # Core modules (always loaded)
    core_directories = {
        "swx_core.models": str(discovery.core_models_path),
        "swx_core.services": str(discovery.core_services_path),
        "swx_core.repositories": str(discovery.core_repositories_path),
        "swx_core.middleware": str(discovery.core_middleware_path),
        "swx_core.auth.admin": str(discovery.core_base / "auth" / "admin"),
        "swx_core.auth.user": str(discovery.core_base / "auth" / "user"),
        "swx_core.auth.core": str(discovery.core_base / "auth" / "core"),
    }

    # Load core modules
    for package, path in core_directories.items():
        modules = dynamic_import(path, package, recursive=True)
        if modules:
            print(f"Loaded {len(modules)} modules from {package}")

    # App modules (only if app exists)
    if discovery.app_exists():
        app_directories = {}

        if discovery.has_models():
            app_directories[discovery.app_models_module] = str(discovery.app_models_path)
        if discovery.has_services():
            app_directories[discovery.app_services_module] = str(discovery.app_services_path)
        if discovery.has_repositories():
            app_directories[discovery.app_repositories_module] = str(discovery.app_repositories_path)
        if discovery.has_middleware():
            app_directories[discovery.app_middleware_module] = str(discovery.app_middleware_path)

        for package, path in app_directories.items():
            modules = dynamic_import(path, package, recursive=True)
            if modules:
                print(f"Loaded {len(modules)} modules from {package}")
    else:
        print(f"App directory '{discovery.app_name}' not found. Skipping app modules.")


def load_middleware(app: FastAPI) -> None:
    """
    Dynamically loads middleware from `swx_core/middleware` and app middleware directory (if exists).

    Args:
        app (FastAPI): The FastAPI application instance.

    Middleware modules must define an `apply_middleware(app: FastAPI)` function to be applied.

    Example:
        ```
        def apply_middleware(app: FastAPI):
            app.add_middleware(SomeMiddleware)
        ```
    """
    # Ensure SessionMiddleware is applied first
    setup_session_middleware(app)

    # Load core middleware (always)
    middleware_modules = dynamic_import(
        str(discovery.core_middleware_path),
        "swx_core.middleware",
        recursive=True
    )

    # Load app middleware (if app exists and has middleware directory)
    if discovery.app_exists() and discovery.has_middleware():
        app_middleware = dynamic_import(
            str(discovery.app_middleware_path),
            discovery.app_middleware_module,
            recursive=True
        )
        middleware_modules.update(app_middleware)

    for module_name, module in middleware_modules.items():
        if hasattr(module, "apply_middleware"):
            try:
                module.apply_middleware(app)
                print(f"Applied middleware: {module_name}")
            except Exception as e:
                print(f"Failed to apply middleware {module_name}: {e}")