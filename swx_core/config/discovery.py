"""
SwX Discovery Configuration.

Makes swx_app paths configurable instead of hardcoded.
This allows swx_core to function as a standalone framework
without requiring a specific app directory structure.

Usage:
    from swx_core.config.discovery import discovery
    
    # Check if app exists
    if discovery.app_exists():
        # Load app-specific modules
        load_app_modules()
    
    # Get configurable paths
    models_path = discovery.app_models_path
    routes_path = discovery.app_routes_path
"""
import os
from pathlib import Path
from typing import Dict, Optional


class DiscoveryConfig:
    """
    Configurable paths for auto-discovery.
    
    Allows swx_app to be optional and configurable via environment variables.
    
    Environment Variables:
        SWX_APP_NAME: Name of the app module (default: "swx_app")
        SWX_APP_BASE: Base directory for app (default: same as SWX_APP_NAME)
    
    Example:
        # Use default swx_app
        discovery = DiscoveryConfig()
        
        # Use custom app name
        os.environ["SWX_APP_NAME"] = "my_app"
        discovery = DiscoveryConfig()
        
        # Use custom app location
        os.environ["SWX_APP_BASE"] = "/path/to/my_app"
        discovery = DiscoveryConfig()
    """
    
    def __init__(self, app_name: Optional[str] = None, app_base: Optional[str] = None):
        """
        Initialize discovery configuration.
        
        Args:
            app_name: Override app module name (default: from SWX_APP_NAME env or "swx_app")
            app_base: Override app base path (default: from SWX_APP_BASE env or app_name)
        """
        # App name (default: swx_app, configurable via env)
        self._app_name = app_name or os.getenv("SWX_APP_NAME", "swx_app")
        
        # Base directory for app (default: same as app_name)
        self._app_base = app_base or os.getenv("SWX_APP_BASE", self._app_name)
        
        # Core directories (always from swx_core)
        self._core_base = Path(__file__).parent.parent  # swx_core/
    
    @property
    def app_name(self) -> str:
        """Get the app module name."""
        return self._app_name
    
    @property
    def app_base(self) -> Path:
        """Get the app base directory as Path."""
        return Path(self._app_base)
    
    @property
    def core_base(self) -> Path:
        """Get the core base directory as Path."""
        return self._core_base
    
    # ==========================================================================
    # App Path Properties
    # ==========================================================================
    
    @property
    def app_models_path(self) -> Path:
        """Path to app models directory."""
        return self.app_base / "models"
    
    @property
    def app_routes_path(self) -> Path:
        """Path to app routes directory."""
        return self.app_base / "routes"
    
    @property
    def app_services_path(self) -> Path:
        """Path to app services directory."""
        return self.app_base / "services"
    
    @property
    def app_repositories_path(self) -> Path:
        """Path to app repositories directory."""
        return self.app_base / "repositories"
    
    @property
    def app_middleware_path(self) -> Path:
        """Path to app middleware directory."""
        return self.app_base / "middleware"
    
    @property
    def app_providers_path(self) -> Path:
        """Path to app providers directory."""
        return self.app_base / "providers"
    
    @property
    def app_listeners_path(self) -> Path:
        """Path to app listeners directory."""
        return self.app_base / "listeners"
    
    @property
    def app_plugins_path(self) -> Path:
        """Path to app plugins directory."""
        return self.app_base / "plugins"
    
    @property
    def app_controllers_path(self) -> Path:
        """Path to app controllers directory."""
        return self.app_base / "controllers"
    
    # ==========================================================================
    # App Module Properties
    # ==========================================================================
    
    @property
    def app_models_module(self) -> str:
        """Fully qualified module name for app models."""
        return f"{self._app_name}.models"
    
    @property
    def app_routes_module(self) -> str:
        """Fully qualified module name for app routes."""
        return f"{self._app_name}.routes"
    
    @property
    def app_services_module(self) -> str:
        """Fully qualified module name for app services."""
        return f"{self._app_name}.services"
    
    @property
    def app_repositories_module(self) -> str:
        """Fully qualified module name for app repositories."""
        return f"{self._app_name}.repositories"
    
    @property
    def app_middleware_module(self) -> str:
        """Fully qualified module name for app middleware."""
        return f"{self._app_name}.middleware"
    
    @property
    def app_providers_module(self) -> str:
        """Fully qualified module name for app providers."""
        return f"{self._app_name}.providers"
    
    @property
    def app_listeners_module(self) -> str:
        """Fully qualified module name for app listeners."""
        return f"{self._app_name}.listeners"
    
    @property
    def app_plugins_module(self) -> str:
        """Fully qualified module name for app plugins."""
        return f"{self._app_name}.plugins"
    
    @property
    def app_controllers_module(self) -> str:
        """Fully qualified module name for app controllers."""
        return f"{self._app_name}.controllers"
    
    # ==========================================================================
    # Core Path Properties
    # ==========================================================================
    
    @property
    def core_models_path(self) -> Path:
        """Path to core models directory."""
        return self.core_base / "models"
    
    @property
    def core_routes_path(self) -> Path:
        """Path to core routes directory."""
        return self.core_base / "routes"
    
    @property
    def core_services_path(self) -> Path:
        """Path to core services directory."""
        return self.core_base / "services"
    
    @property
    def core_repositories_path(self) -> Path:
        """Path to core repositories directory."""
        return self.core_base / "repositories"
    
    @property
    def core_middleware_path(self) -> Path:
        """Path to core middleware directory."""
        return self.core_base / "middleware"
    
    @property
    def core_providers_path(self) -> Path:
        """Path to core providers directory."""
        return self.core_base / "providers"
    
    # ==========================================================================
    # Utility Methods
    # ==========================================================================
    
    def app_exists(self) -> bool:
        """
        Check if the app directory exists.
        
        Returns:
            bool: True if app_base directory exists, False otherwise.
        """
        return self.app_base.exists()
    
    def has_models(self) -> bool:
        """Check if app has a models directory."""
        return self.app_models_path.exists()
    
    def has_routes(self) -> bool:
        """Check if app has a routes directory."""
        return self.app_routes_path.exists()
    
    def has_providers(self) -> bool:
        """Check if app has a providers directory."""
        return self.app_providers_path.exists()
    
    def has_listeners(self) -> bool:
        """Check if app has a listeners directory."""
        return self.app_listeners_path.exists()
    
    def has_plugins(self) -> bool:
        """Check if app has a plugins directory."""
        return self.app_plugins_path.exists()
    
    def get_modules_to_scan(self) -> Dict[str, str]:
        """
        Get all modules to scan for auto-discovery.
        
        Returns:
            Dict mapping module names to their paths.
            Only includes app modules if app directory exists.
        """
        modules = {
            # Core modules (always included)
            "swx_core.models": str(self.core_models_path),
            "swx_core.services": str(self.core_services_path),
            "swx_core.repositories": str(self.core_repositories_path),
            "swx_core.middleware": str(self.core_middleware_path),
        }
        
        # Only add app modules if app exists
        if self.app_exists():
            if self.has_models():
                modules[self.app_models_module] = str(self.app_models_path)
            if self.has_services():
                modules[self.app_services_module] = str(self.app_services_path)
            if self.has_repositories():
                modules[self.app_repositories_module] = str(self.app_repositories_path)
            if self.has_middleware():
                modules[self.app_middleware_module] = str(self.app_middleware_path)
        
        return modules
    
    def has_middleware(self) -> bool:
        """Check if app has a middleware directory."""
        return self.app_middleware_path.exists()
    
    def has_services(self) -> bool:
        """Check if app has a services directory."""
        return self.app_services_path.exists()
    
    def has_repositories(self) -> bool:
        """Check if app has a repositories directory."""
        return self.app_repositories_path.exists()
    
    def __repr__(self) -> str:
        """String representation of discovery config."""
        return (
            f"DiscoveryConfig("
            f"app_name='{self._app_name}', "
            f"app_base='{self._app_base}', "
            f"app_exists={self.app_exists()})"
        )


# Global discovery config instance
# Can be overridden by setting SWX_APP_NAME or SWX_APP_BASE environment variables
discovery = DiscoveryConfig()


def get_discovery() -> DiscoveryConfig:
    """
    Get the global discovery configuration instance.
    
    Returns:
        DiscoveryConfig: The global discovery configuration.
    """
    return discovery


def reset_discovery(app_name: Optional[str] = None, app_base: Optional[str] = None) -> DiscoveryConfig:
    """
    Reset the global discovery configuration with new settings.
    
    This is useful for testing or when you need to change the app
    configuration at runtime.
    
    Args:
        app_name: New app module name.
        app_base: New app base path.
    
    Returns:
        DiscoveryConfig: The new global discovery configuration.
    """
    global discovery
    discovery = DiscoveryConfig(app_name=app_name, app_base=app_base)
    return discovery