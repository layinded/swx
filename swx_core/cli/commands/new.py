"""
SwX Project Scaffolding Command.

Creates a new SwX project from built-in templates.
"""
import os
import shutil
import json
import secrets
from pathlib import Path
from typing import Optional

import click

# Template directory location (relative to this file)
TEMPLATE_DIR = Path(__file__).parent.parent / "template" / "project"


class TemplateRenderer:
    """Renders project templates with variable substitution."""

    def __init__(self, context: dict):
        """
        Initialize renderer with context variables.

        Args:
            context: Dictionary of template variables
        """
        self.context = context

    def render_file(self, source: Path, dest: Path) -> None:
        """
        Render a single file with context substitution.

        Args:
            source: Source template file path
            dest: Destination file path
        """
        # Binary files should be copied directly
        binary_extensions = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip"}
        if source.suffix in binary_extensions:
            shutil.copy2(source, dest)
            return

        try:
            content = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # If we can't decode as text, copy as binary
            shutil.copy2(source, dest)
            return

        # Replace {{ variable }} placeholders
        for key, value in self.context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
            content = content.replace(f"{{{{{key}}}}}", str(value))

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    def render_directory(self, source: Path, dest: Path) -> None:
        """
        Recursively render a directory.

        Args:
            source: Source directory path
            dest: Destination directory path
        """
        if not source.exists():
            raise FileNotFoundError(f"Template directory not found: {source}")

        for item in source.iterdir():
            if item.is_file():
                # Skip template.json (not needed in output)
                if item.name == "template.json":
                    continue

                # Render filename with placeholders
                dest_name = item.name
                for key, value in self.context.items():
                    dest_name = dest_name.replace(f"{{{{{key}}}}}", str(value))

                self.render_file(item, dest / dest_name)
            else:
                # Render directory name with placeholders
                dest_name = item.name
                for key, value in self.context.items():
                    dest_name = dest_name.replace(f"{{{{{key}}}}}", str(value))

                # Skip certain directories
                if dest_name in {"__pycache__", ".git", ".venv", "node_modules"}:
                    continue

                self.render_directory(item, dest / dest_name)


@click.command("new")
@click.argument("project_name")
@click.option("--path", "-p", default=".", help="Directory to create project in")
@click.option("--docker/--no-docker", default=True, help="Include Docker files (default: yes)")
@click.option("--celery/--no-celery", default=True, help="Include Celery setup (default: yes)")
@click.option("--redis/--no-redis", default=True, help="Include Redis configuration (default: yes)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing directory")
def new_project(
    project_name: str,
    path: str,
    docker: bool,
    celery: bool,
    redis: bool,
    force: bool
):
    """
    Create a new SwX project.

    Creates a complete project structure with all necessary files
    for building a SwX application.

    Example:
        swx new my_project
        swx new my_project --path ./projects
        swx new my_project --no-docker
    """
    click.secho(f"\n🚀 Creating SwX project: {project_name}\n", fg="cyan", bold=True)

    # Validate project name
    if not project_name.isidentifier():
        click.secho("❌ Project name must be a valid Python identifier", fg="red")
        click.secho("   Use letters, numbers, and underscores only. Cannot start with a number.", fg="yellow")
        raise SystemExit(1)

    # Determine project directory
    project_dir = Path(path) / project_name

    if project_dir.exists():
        if not force:
            click.secho(f"❌ Directory '{project_dir}' already exists", fg="red")
            click.secho("   Use --force to overwrite", fg="yellow")
            raise SystemExit(1)

        # Ask for confirmation before overwriting
        if not click.confirm(f"Directory '{project_dir}' exists. Overwrite?", default=False):
            click.secho("Aborted.", fg="yellow")
            raise SystemExit(0)
        shutil.rmtree(project_dir)

    # Prepare template context
    context = {
        "project_name": project_name,
        "project_slug": project_name.lower().replace("-", "_").replace(" ", "_"),
        "project_title": project_name.replace("_", " ").replace("-", " ").title(),
    }

    # Check for template directory
    if not TEMPLATE_DIR.exists():
        click.secho(f"❌ Template directory not found: {TEMPLATE_DIR}", fg="red")
        click.secho("   Make sure swx-core is properly installed", fg="yellow")
        raise SystemExit(1)

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)
    click.secho(f"✅ Created directory: {project_dir}", fg="green")

    # Render template
    renderer = TemplateRenderer(context)

    try:
        renderer.render_directory(TEMPLATE_DIR, project_dir)
        click.secho("✅ Created project structure", fg="green")
    except Exception as e:
        click.secho(f"❌ Error rendering template: {e}", fg="red")
        shutil.rmtree(project_dir)
        raise SystemExit(1)

    # Create .env from .env.example
    env_example = project_dir / ".env.example"
    env_file = project_dir / ".env"
    if env_example.exists() and not env_file.exists():
        env_content = env_example.read_text()
        env_content = env_content.replace("your-super-secret-key-change-this-in-production", secrets.token_urlsafe(32))
        env_content = env_content.replace("your-refresh-secret-key-change-this-in-production", secrets.token_urlsafe(32))
        env_content = env_content.replace("your-password-reset-secret-key-change-this-in-production", secrets.token_urlsafe(32))
        env_content = env_content.replace("changethispassword", secrets.token_urlsafe(16))
        env_file.write_text(env_content)
        click.secho("✅ Created .env file with generated secrets", fg="green")

    # Remove optional files based on flags
    if not docker:
        for f in ["Dockerfile", "docker-compose.yml", "docker-compose.prod.yml", ".dockerignore"]:
            dockerfile = project_dir / f
            if dockerfile.exists():
                dockerfile.unlink()
        click.secho("   Skipping Docker files", fg="yellow")

    # Print next steps
    click.secho(f"\n✨ Project '{project_name}' created successfully!\n", fg="green", bold=True)
    click.secho("Next steps:\n", fg="cyan")
    click.echo(f"  1. cd {project_name}")
    click.echo( "  2. python -m venv .venv && source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate")
    click.echo( "  3. pip install swx-core")
    click.echo( "  4. swx setup")
    click.echo( "  5. swx serve\n")
    click.secho("Documentation: https://swx-framework.readthedocs.io", fg="blue")


@click.command("init")
@click.option("--path", "-p", default=".", help="Initialize in current directory")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
def init_project(path: str, force: bool):
    """
    Initialize SwX in an existing project.

    Creates the swx_app directory structure and necessary configuration
    files in the current directory.

    Example:
        swx init
        swx init --force
    """
    click.secho("\n🔧 Initializing SwX in current directory\n", fg="cyan")

    project_dir = Path(path)

    # Create swx_app structure
    dirs_to_create = [
        "swx_app/models",
        "swx_app/routes",
        "swx_app/controllers",
        "swx_app/services",
        "swx_app/repositories",
        "swx_app/providers",
        "swx_app/listeners",
        "swx_app/middleware",
        "swx_app/plugins",
        "migrations/versions",
        "tests",
    ]

    for dir_path in dirs_to_create:
        full_path = project_dir / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        click.secho(f"  ✅ Created {dir_path}/", fg="green")

    # Create __init__.py files
    init_dirs = [
        "swx_app",
        "swx_app/models",
        "swx_app/routes",
        "swx_app/controllers",
        "swx_app/services",
        "swx_app/repositories",
        "swx_app/providers",
        "swx_app/listeners",
        "swx_app/middleware",
        "swx_app/plugins",
        "tests",
    ]

    project_title = project_dir.name.replace("_", " ").replace("-", " ").title()

    for dir_path in init_dirs:
        init_file = project_dir / dir_path / "__init__.py"
        if not init_file.exists() or force:
            init_file.write_text(f'"""{project_title} Application."""\n')

    # Create default app_provider.py
    provider_file = project_dir / "swx_app/providers/app_provider.py"
    if not provider_file.exists() or force:
        provider_file.write_text(f'''"""
{project_title} - Application Service Provider.

Override core services or add custom bindings here.
"""

from swx_core.providers.base import ServiceProvider


class AppServiceProvider(ServiceProvider):
    """
    Main application service provider for customizations.
    
    Override any core service:
    
        def register(self):
            # Use custom rate limiter
            self.singleton("rate_limiter", MyCustomRateLimiter)
            
            # Use custom billing provider
            self.singleton("billing.provider", MyCustomBillingProvider)
    
    """
    
    priority = 1000  # Run last to override core services
    
    def register(self) -> None:
        """User service overrides go here."""
        pass
    
    def boot(self) -> None:
        """Post-registration configuration."""
        pass
''')
        click.secho("  ✅ Created swx_app/providers/app_provider.py", fg="green")

    # Create plugin manifest
    manifest_file = project_dir / "swx_app/plugins/manifest.json"
    if not manifest_file.exists() or force:
        manifest_file.write_text(json.dumps({
            "plugins": {},
            "enabled": [],
            "version": "1.0.0"
        }, indent=2))
        click.secho("  ✅ Created swx_app/plugins/manifest.json", fg="green")

    # Create .env.example if not exists
    env_example = project_dir / ".env.example"
    if not env_example.exists():
        env_example.write_text(f'''# SwX Configuration for {project_title}
PROJECT_NAME={project_dir.name}
ENVIRONMENT=local
DOCKERIZED=false

# Security - UPDATE THESE!
SECRET_KEY=your-secret-key-here
REFRESH_SECRET_KEY=your-refresh-secret-here

# Database
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=changeme
DB_NAME={project_dir.name}_db

# Redis
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379

# Superuser
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethis
''')
        click.secho("  ✅ Created .env.example", fg="green")

    click.secho(f"\n✨ SwX initialized successfully!\n", fg="green", bold=True)
    click.secho("Next steps:\n", fg="cyan")
    click.echo("  1. pip install swx-core")
    click.echo("  2. cp .env.example .env  # Then edit .env")
    click.echo("  3. swx setup")
    click.echo("  4. swx serve\n")