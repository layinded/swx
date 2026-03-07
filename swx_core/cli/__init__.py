"""
SwX CLI Package
"""

# Main make_group for resource generation
from swx_core.cli.commands.make import (
    make_group,
    controller,
    model,
    repository,
    route,
    service,
    resource,
)

__all__ = [
    "make_group",
    "controller",
    "model",
    "repository",
    "route",
    "service",
    "resource",
]