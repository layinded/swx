import click
import sys
import os

# Import essential commands
from swx_core.cli.commands.db import db
from swx_core.cli.commands.make import make_group
from swx_core.cli.commands.tinker import tinker
from swx_core.cli.commands.format import format
from swx_core.cli.commands.lint import lint
from swx_core.cli.commands.new import new_project, init_project

@click.group()
@click.version_option(version="2.0.0", prog_name="swx")
def main():
    """SwX CLI - Production-grade FastAPI framework management.
    
    § Commands:
    
        Core:
            swx setup          Interactive setup wizard
            swx serve          Start development server
            swx down           Enable maintenance mode
            swx up             Disable maintenance mode
            swx optimize       Cache routes and config
            swx upgrade        Upgrade the framework
        
        Database:
            swx db setup       Setup database
            swx db migrate     Run migrations
            swx db revision    Create migration
            swx db downgrade   Rollback migration
            swx db seed        Seed database
        
        Code Generation:
            swx make resource  Generate full CRUD scaffold
            swx make model     Generate model
            swx make:from-model Generate from existing model
        
        Routes & Config:
            swx route:list     List all routes
            swx config:cache   Cache configuration
            swx config:clear   Clear config cache
        
        Plugins:
            swx plugin:list    List plugins
            swx plugin:enable  Enable plugin
            swx plugin:disable Disable plugin
            swx plugin:install Install plugin
        
        Dev Tools:
            swx tinker         Interactive shell
            swx format         Format code
            swx lint           Lint code
    """
    pass


# ============================================================
# Register Commands
# ============================================================

from swx_core.cli.commands.framework import register_framework_commands

# Framework commands (setup, serve, down, up, optimize, upgrade, etc.)
register_framework_commands(main)

# Database management
main.add_command(db, "db")

# Code scaffolding
main.add_command(make_group, "make")

# Interactive shell
main.add_command(tinker, "tinker")

# Code quality
main.add_command(format, "format")
main.add_command(lint, "lint")

# Project management
main.add_command(new_project, "new")
main.add_command(init_project, "init")


if __name__ == "__main__":
    main(prog_name="swx")  # ✅ CLI Entry Point