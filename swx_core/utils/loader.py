"""
Module Loader
-------------
This module dynamically loads and imports:
- Models, services, repositories, and middleware from both `swx_core/` and app directories.
- Middleware components that define an `apply_middleware(app: FastAPI)` function.

Features:
- Recursively imports all submodules in specified directories.
- Resolves module dependencies via topological sort before loading.
- Reloads already imported modules for real-time updates.
- Ensures middleware is loaded properly in FastAPI applications.
- Uses configurable discovery for app paths (no hardcoded swx_app).

Functions:
- `dynamic_import()`: Dynamically imports all modules within a specified path.
- `load_all_modules()`: Loads models, services, repositories, and middleware dynamically.
- `load_middleware()`: Loads and applies middleware to a FastAPI application.
"""

import ast
import importlib
import pkgutil
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Any, List, Set

from fastapi import FastAPI

from swx_core.middleware.logging_middleware import logger
from swx_core.middleware.session_middleware import setup_session_middleware
from swx_core.config.discovery import discovery

_loading_modules: set[str] = set()


def _extract_imports_from_file(file_path: Path, package_name: str) -> Set[str]:
    """Parse a Python file and extract intra-package import dependencies.

    Only returns imports that are within the same top-level package
    (e.g., swx_core.services.billing.enforcement importing
    swx_core.services.billing.entitlement_resolver).

    Args:
        file_path: Path to the .py file.
        package_name: The package prefix (e.g., "swx_core.services").

    Returns:
        Set of fully-qualified module names that this file imports from
        within the same package group.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return set()

    deps = set()
    top_level = package_name.split(".")[0]

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None:
            continue
        if not node.module.startswith(top_level + "."):
            continue
        deps.add(node.module)

    return deps


def _topological_sort(
    modules: List[str],
    dep_graph: Dict[str, Set[str]],
) -> List[str]:
    """Sort modules so that dependencies are loaded before dependents.

    Uses Kahn's algorithm (BFS-based topological sort). Modules with
    no dependencies or whose dependencies are outside the current set
    are loaded first. Cycles are broken by loading the remaining modules
    in their original order.

    Args:
        modules: List of fully-qualified module names to sort.
        dep_graph: Mapping from module name to its intra-package dependencies.

    Returns:
        List of module names in dependency-safe loading order.
    """
    module_set = set(modules)
    in_degree: Dict[str, int] = defaultdict(int)
    dependents: Dict[str, List[str]] = defaultdict(list)

    for mod in modules:
        in_degree.setdefault(mod, 0)

    for mod in modules:
        for dep in dep_graph.get(mod, set()):
            if dep in module_set:
                in_degree[mod] += 1
                dependents[dep].append(mod)

    queue = deque(m for m in modules if in_degree[m] == 0)
    result = []

    while queue:
        mod = queue.popleft()
        result.append(mod)
        for dependent in dependents.get(mod, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Remaining modules have circular deps — append in original order
    for mod in modules:
        if mod not in result:
            result.append(mod)

    return result


def dynamic_import(base_path: str, package_name: str, recursive: bool = False) -> Dict[str, Any]:
    """Dynamically imports all modules within the given path.

    Resolves module dependencies via topological sort before loading,
    preventing ImportError from partially-initialized modules when
    module A imports from module B and is loaded first.

    Args:
        base_path: The base directory path to search for modules.
        package_name: The package name associated with the base path.
        recursive: Whether to recursively import submodules.

    Returns:
        Dictionary where keys are module names and values are imported modules.
    """
    imported_modules = {}
    package_path = Path(base_path).resolve()

    if not package_path.exists():
        logger.debug(f"Path does not exist, skipping: {base_path}")
        return imported_modules

    # Phase 1: Discover modules and build dependency graph
    discovered = []
    dep_graph: Dict[str, Set[str]] = defaultdict(set)

    for _finder, mod_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
        full_module_name = f"{package_name}.{mod_name}"
        discovered.append((full_module_name, is_pkg))

        if not is_pkg:
            mod_file = package_path / f"{mod_name}.py"
            deps = _extract_imports_from_file(mod_file, package_name)
            dep_graph[full_module_name] = deps

    # Phase 2: Topological sort for dependency-safe loading order
    module_names = [name for name, _ in discovered]
    sorted_names = _topological_sort(module_names, dep_graph)
    is_pkg_map = {name: is_pkg for name, is_pkg in discovered}

    # Phase 3: Load modules in dependency order
    for full_module_name in sorted_names:
        is_pkg = is_pkg_map.get(full_module_name, False)

        try:
            skip_reload = ".models." in full_module_name

            if full_module_name in sys.modules:
                if full_module_name in _loading_modules:
                    logger.debug(f"Skipping {full_module_name} - already in loading state")
                    imported_modules[full_module_name] = sys.modules[full_module_name]
                    continue

                if not skip_reload:
                    _loading_modules.add(full_module_name)
                    try:
                        importlib.reload(sys.modules[full_module_name])
                        logger.info(f"Reloaded module: {full_module_name}")
                    finally:
                        _loading_modules.discard(full_module_name)
            else:
                module = importlib.import_module(full_module_name)
                sys.modules[full_module_name] = module
                logger.info(f"Loaded new module: {full_module_name}")

            is_route_dir = ".routes." in full_module_name
            if not (is_route_dir and is_pkg):
                imported_modules[full_module_name] = sys.modules[full_module_name]

            if recursive and is_pkg:
                subdir_path = package_path / full_module_name.split(".")[-1]
                submodules = dynamic_import(str(subdir_path), full_module_name, recursive=True)
                imported_modules.update(submodules)

        except Exception as e:
            logger.error(f"Error loading {full_module_name}: {e}\n{__import__('traceback').format_exc()}")

    return imported_modules


def load_all_modules() -> None:
    """Loads models, services, repositories, and middleware dynamically.

    Uses configurable discovery to determine which app modules to load.
    If the app directory doesn't exist, only core modules are loaded.
    """
    core_directories = {
        "swx_core.models": str(discovery.core_models_path),
        "swx_core.services": str(discovery.core_services_path),
        "swx_core.repositories": str(discovery.core_repositories_path),
        "swx_core.middleware": str(discovery.core_middleware_path),
        "swx_core.auth.admin": str(discovery.core_base / "auth" / "admin"),
        "swx_core.auth.user": str(discovery.core_base / "auth" / "user"),
        "swx_core.auth.core": str(discovery.core_base / "auth" / "core"),
    }

    for package, path in core_directories.items():
        modules = dynamic_import(path, package, recursive=True)
        if modules:
            print(f"Loaded {len(modules)} modules from {package}")

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


def load_all_listeners() -> None:
    """Load and register all event listeners from core and app directories.

    This should be called during application startup, after models and services
    are loaded but before handling requests.
    """
    from swx_core.events.listener_loader import load_listeners_from_path

    total_registered = 0

    core_listeners_path = discovery.core_base / "events" / "listeners"
    if core_listeners_path.exists():
        count = load_listeners_from_path(
            str(core_listeners_path),
            "swx_core.events.listeners"
        )
        if count:
            print(f"Registered {count} core listeners")
            total_registered += count

    if discovery.app_exists():
        app_listeners_path = discovery.app_base / "listeners"
        if app_listeners_path.exists():
            app_listeners_module = f"{discovery.app_name}.listeners"
            count = load_listeners_from_path(
                str(app_listeners_path),
                app_listeners_module
            )
            if count:
                print(f"Registered {count} app listeners")
                total_registered += count

    if total_registered == 0:
        print("No listeners found to register")
    else:
        print(f"Total listeners registered: {total_registered}")


def load_middleware(app: FastAPI) -> None:
    """Dynamically loads middleware from swx_core/middleware and app middleware.

    Args:
        app: The FastAPI application instance.

    Middleware modules must define an `apply_middleware(app: FastAPI)` function.
    """
    setup_session_middleware(app)

    middleware_modules = dynamic_import(
        str(discovery.core_middleware_path),
        "swx_core.middleware",
        recursive=True
    )

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
