"""
SwX AI-Aware Layer - Contract Registry Exporter
============================================

Exports ABC interfaces, method signatures, and override instructions.
"""

import inspect
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from swx_core.repositories.base import BaseRepository
except ImportError:
    BaseRepository = None

try:
    from swx_core.services.base import BaseService
except ImportError:
    BaseService = None

try:
    from swx_core.controllers.base import BaseController
except ImportError:
    BaseController = None

try:
    from swx_core.providers.base import ServiceProvider
except ImportError:
    ServiceProvider = None


def get_contracts_export(
    interface: Optional[str] = None,
    include_implementations: bool = False
) -> Dict[str, Any]:
    """Export contract registry."""
    
    contracts = []
    
    if BaseRepository:
        contracts.append(_extract_repository_contract(BaseRepository))
    
    if BaseService:
        contracts.append(_extract_service_contract(BaseService))
    
    if BaseController:
        contracts.append(_extract_controller_contract(BaseController))
    
    if ServiceProvider:
        contracts.append(_extract_provider_contract(ServiceProvider))
    
    if interface:
        contracts = [c for c in contracts if c["name"] == interface]
    
    return {
        "version": "1.0.0",
        "generated_at": "2026-03-08T12:00:00Z",
        "contracts": contracts
    }


def _extract_repository_contract(cls) -> Dict[str, Any]:
    """Extract BaseRepository contract."""
    
    methods = []
    
    for name in ["find_by_id", "find_all", "create", "update", "delete", "search", "paginate"]:
        if hasattr(cls, name):
            method = getattr(cls, name)
            sig = inspect.signature(method)
            
            methods.append({
                "name": name,
                "signature": str(sig),
                "return_type": _get_return_type(method),
                "is_async": inspect.iscoroutinefunction(method),
                "is_abstract": getattr(method, "__isabstractmethod__", False),
                "override_instructions": _get_repo_override_instructions(name)
            })
    
    return {
        "name": "RepositoryProtocol",
        "path": "swx_core.repositories.base.BaseRepository",
        "type": "abstract_base_class",
        "description": "Base repository interface with async CRUD operations",
        "methods": methods,
        "implementations": ["swx_core.repositories.UserRepository"]
    }


def _extract_service_contract(cls) -> Dict[str, Any]:
    """Extract BaseService contract."""
    
    methods = []
    
    for name in ["get", "create", "update", "delete", "list"]:
        if hasattr(cls, name):
            method = getattr(cls, name)
            sig = inspect.signature(method)
            
            methods.append({
                "name": name,
                "signature": str(sig),
                "return_type": _get_return_type(method),
                "is_async": inspect.iscoroutinefunction(method),
                "is_abstract": getattr(method, "__isabstractmethod__", False),
                "override_instructions": _get_service_override_instructions(name)
            })
    
    return {
        "name": "ServiceProtocol",
        "path": "swx_core.services.base.BaseService",
        "type": "abstract_base_class",
        "description": "Base service layer with business logic",
        "methods": methods,
        "implementations": []
    }


def _extract_controller_contract(cls) -> Dict[str, Any]:
    """Extract BaseController contract."""
    
    methods = []
    
    for name in ["get", "create", "update", "delete", "list"]:
        if hasattr(cls, name):
            method = getattr(cls, name)
            sig = inspect.signature(method)
            
            methods.append({
                "name": name,
                "signature": str(sig),
                "return_type": _get_return_type(method),
                "is_async": inspect.iscoroutinefunction(method),
                "is_abstract": getattr(method, "__isabstractmethod__", False),
                "override_instructions": _get_controller_override_instructions(name)
            })
    
    return {
        "name": "ControllerProtocol",
        "path": "swx_core.controllers.base.BaseController",
        "type": "abstract_base_class",
        "description": "Base REST controller with CRUD endpoints",
        "methods": methods,
        "implementations": []
    }


def _extract_provider_contract(cls) -> Dict[str, Any]:
    """Extract ServiceProvider contract."""
    
    methods = []
    
    for name in ["register", "boot"]:
        if hasattr(cls, name):
            method = getattr(cls, name)
            sig = inspect.signature(method)
            
            methods.append({
                "name": name,
                "signature": str(sig),
                "return_type": "None",
                "is_async": inspect.iscoroutinefunction(method),
                "is_abstract": getattr(method, "__isabstractmethod__", False),
                "override_instructions": _get_provider_override_instructions(name)
            })
    
    return {
        "name": "ProviderProtocol",
        "path": "swx_core.providers.base.ServiceProvider",
        "type": "abstract_base_class",
        "description": "Service provider for registering services",
        "methods": methods,
        "implementations": ["swx_core.providers.database_provider.DatabaseServiceProvider"]
    }


def _get_return_type(method) -> str:
    """Get return type annotation."""
    if hasattr(method, "__annotations__"):
        annotations = method.__annotations__
        if "return" in annotations:
            return str(annotations["return"])
    return "Any"


def _get_repo_override_instructions(method_name: str) -> str:
    """Get override instructions for repository methods."""
    instructions = {
        "find_by_id": "Query database by primary key. Return None if not found.",
        "find_all": "Apply filters and pagination. Return empty list if no results.",
        "create": "Create new record from data dict. Return created instance.",
        "update": "Update existing record. Return updated instance or None.",
        "delete": "Delete record by ID. Return True if deleted, False if not found.",
        "search": "Perform full-text search. Return matching records.",
        "paginate": "Return paginated results with total count."
    }
    return instructions.get(method_name, "Implement the method.")


def _get_service_override_instructions(method_name: str) -> str:
    """Get override instructions for service methods."""
    instructions = {
        "get": "Retrieve entity by ID. Apply authorization checks.",
        "create": "Create new entity. Validate data. Emit events.",
        "update": "Update existing entity. Validate data. Emit events.",
        "delete": "Soft-delete entity. Emit deletion event.",
        "list": "List entities with filtering and pagination."
    }
    return instructions.get(method_name, "Implement the method.")


def _get_controller_override_instructions(method_name: str) -> str:
    """Get override instructions for controller methods."""
    instructions = {
        "get": "Handle GET single entity. Return 404 if not found.",
        "create": "Handle POST create. Validate request body. Return 201.",
        "update": "Handle PUT/PATCH update. Return 404 if not found.",
        "delete": "Handle DELETE. Return 204 on success.",
        "list": "Handle GET list with query parameters."
    }
    return instructions.get(method_name, "Implement the endpoint.")


def _get_provider_override_instructions(method_name: str) -> str:
    """Get override instructions for provider methods."""
    instructions = {
        "register": "Register service bindings with container.",
        "boot": "Boot services after all providers registered."
    }
    return instructions.get(method_name, "Implement the method.")