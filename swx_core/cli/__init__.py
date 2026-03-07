"""
SwX CLI Package
"""

from swx_core.cli.commands.make import cli, model, controller, service, repository, route, resource

__all__ = [
    "cli",
    "model",
    "controller",
    "service",
    "repository",
    "route",
    "resource",
]