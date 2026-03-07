"""
Model Loader
------------
This module dynamically loads (and reloads) all SQLAlchemy models
from both app models directory and swx_core.models to ensure
they are registered with `Base.metadata`.

Features:
- Dynamically imports and reloads models.
- Ensures that models are registered properly with SQLAlchemy.
- Provides debug logging for model imports.
- Uses configurable discovery for app paths.

Functions:
- `load_all_models()`: Dynamically loads all models and registers them with `Base.metadata`.
"""
import sys
import importlib
import pkgutil

import click

from swx_core.models.base import Base
from swx_core.config.discovery import discovery


def load_all_models() -> Base:
    """
       Dynamically loads (and reloads) all SQLAlchemy models from both app models
       and swx_core.models so that they register with `Base.metadata`.

       Behavior:
           - Scans app.models and swx_core.models for SQLAlchemy models.
           - Only loads app models if app directory exists.
           - Reloads modules to ensure up-to-date registrations.
           - Attaches all public attributes from submodules to the parent module.

       Returns:
           Base: The SQLAlchemy Base class with registered models.

       Logs:
           - Imported parent modules.
           - Reloaded submodules.
           - Attached public attributes from submodules to parent modules.

       Example:
           ```
           from swx_core.utils.model import load_all_models
           Base = load_all_models()
           ```
       """
    importlib.invalidate_caches()

    # Build list of modules to scan
    modules_to_scan = ["swx_core.models"]

    # Add app models if app exists and has models directory
    if discovery.app_exists() and discovery.has_models():
        modules_to_scan.append(discovery.app_models_module)

    for module_name in modules_to_scan:
        try:
            if module_name not in sys.modules:
                # Check if this is an app module and the path exists
                if module_name == discovery.app_models_module:
                    if not discovery.app_models_path.exists():
                        click.echo(f"Warning: App models directory not found at {discovery.app_models_path}. Skipping...")
                        continue

                parent_module = importlib.import_module(module_name)
                click.echo(f"DEBUG: Imported parent module: {module_name}")
            else:
                parent_module = sys.modules[module_name]

            # If it's a package, walk through submodules
            if hasattr(parent_module, "__path__"):
                for finder, name, is_pkg in pkgutil.walk_packages(
                        parent_module.__path__, parent_module.__name__ + "."
                ):
                    if is_pkg:
                        continue

                    # Use sys.modules cache to avoid reloading
                    if name in sys.modules:
                        mod = sys.modules[name]
                    else:
                        mod = importlib.import_module(name)

                    click.echo(f"DEBUG: Loaded submodule: {name}")

                    # Attach all public attributes from submodule to parent
                    for attr in dir(mod):
                        if not attr.startswith("_"):
                            setattr(parent_module, attr, getattr(mod, attr))
                            click.echo(f"DEBUG: Attached {attr} from {name} to {module_name}")

        except ModuleNotFoundError:
            click.echo(f"Warning: Module {module_name} not found. Skipping...", err=True)

    click.echo(f"DEBUG: Loaded models in metadata: {list(Base.metadata.tables.keys())}")
    return Base