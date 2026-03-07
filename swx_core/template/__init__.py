"""
SwX Project Templates.

This module provides project templates for scaffolding new SwX projects.
Templates are bundled with the package and copied during `swx new`.
"""

import os
from pathlib import Path

# Template directory location
TEMPLATE_DIR = Path(__file__).parent / "project"


def get_template_dir() -> Path:
    """
    Get the template directory path.
    
    Returns:
        Path: Path to the project template directory.
    """
    return TEMPLATE_DIR


def get_template_path(name: str) -> Path:
    """
    Get a specific template file or directory.
    
    Args:
        name: Name of the template item (e.g., "app", "migrations")
    
    Returns:
        Path: Path to the template item.
    """
    return TEMPLATE_DIR / name