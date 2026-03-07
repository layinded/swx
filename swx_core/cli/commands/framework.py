"""
SwX Framework CLI Commands.

Production-grade CLI commands for framework lifecycle management:
- setup: Interactive setup wizard
- serve: Development server
- down/up: Maintenance mode
- optimize: Cache routes/config
- route:list: List all routes
- config:cache/clear: Configuration caching
- publish: Publish core assets
- plugin:*: Plugin management
- upgrade: Framework upgrade
"""

import os
import sys
import json
import shutil
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import click

# ===================== CONSTANTS =====================

MAINTENANCE_FILE = "storage/framework/maintenance"
ROUTE_CACHE_FILE = "storage/framework/cache/routes.json"
CONFIG_CACHE_FILE = "storage/framework/cache/config.json"
ENV_EXAMPLE_FILE = ".env.example"
ENV_FILE = ".env"


def _get_plugin_manifest_path() -> str:
    """Get the plugin manifest path using configurable discovery."""
    from swx_core.config.discovery import discovery
    return str(discovery.app_plugins_path / "manifest.json")

# ===================== SETUP COMMAND =====================

@click.command()
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
@click.option("--no-db", is_flag=True, help="Skip database setup")
@click.option("--no-superuser", is_flag=True, help="Skip superuser creation")
def setup(force: bool, no_db: bool, no_superuser: bool):
    """
    Interactive setup wizard for SwX framework.
    
    Creates .env file, runs database migrations, and creates superuser.
    
    Example:
        swx setup
        swx setup --force
        swx setup --no-db
    """
    click.secho("\n🚀 SwX Framework Setup Wizard\n", fg="cyan", bold=True)
    
    # Step 1: Environment file
    if os.path.exists(ENV_FILE) and not force:
        click.secho("✅ .env file already exists", fg="green")
    else:
        _setup_env_file()
    
    # Step 2: Storage directories
    _setup_storage_directories()
    
    # Step 3: Plugin manifest
    _setup_plugin_manifest()
    
    # Step 4: Database setup
    if not no_db:
        _setup_database()
    
    # Step 5: Superuser creation
    if not no_superuser:
        _create_superuser()
    
    click.secho("\n✨ SwX Framework setup complete!", fg="green", bold=True)
    click.secho("Run 'swx serve' to start the development server.\n", fg="cyan")


def _setup_env_file():
    """Create .env file from .env.example with interactive prompts."""
    click.secho("\n📝 Setting up environment file...", fg="cyan")
    
    if not os.path.exists(ENV_EXAMPLE_FILE):
        click.secho("⚠️  No .env.example found, creating minimal .env", fg="yellow")
        env_content = _get_default_env()
    else:
        with open(ENV_EXAMPLE_FILE, "r") as f:
            env_content = f.read()
    
    # Interactive configuration
    click.secho("\nConfigure your environment (press Enter to use defaults):\n", fg="cyan")
    
    # Database configuration
    db_host = click.prompt("Database host", default="localhost")
    db_port = click.prompt("Database port", default="5432")
    db_name = click.prompt("Database name", default="swx_db")
    db_user = click.prompt("Database user", default="swx_user")
    db_password = click.prompt("Database password", hide_input=True, default="")
    
    # Replace placeholders
    env_content = env_content.replace("DB_HOST=localhost", f"DB_HOST={db_host}")
    env_content = env_content.replace("DB_PORT=5432", f"DB_PORT={db_port}")
    env_content = env_content.replace("DB_NAME=swx_db", f"DB_NAME={db_name}")
    env_content = env_content.replace("DB_USER=swx_user", f"DB_USER={db_user}")
    if db_password:
        env_content = env_content.replace("DB_PASSWORD=", f"DB_PASSWORD={db_password}")
    
    # Generate secret key if not present
    if "SECRET_KEY=" in env_content and "your-secret-key" in env_content:
        import secrets
        secret_key = secrets.token_urlsafe(32)
        env_content = env_content.replace(
            "SECRET_KEY=your-secret-key-change-in-production",
            f"SECRET_KEY={secret_key}"
        )
    
    with open(ENV_FILE, "w") as f:
        f.write(env_content)
    
    click.secho("✅ Created .env file", fg="green")


def _get_default_env() -> str:
    """Return default .env content."""
    import secrets
    secret_key = secrets.token_urlsafe(32)
    
    return f"""# SwX Framework Environment Configuration
# Generated on {datetime.now().isoformat()}

# Application
APP_NAME=SwX-API
APP_ENV=local
APP_DEBUG=true
SECRET_KEY={secret_key}

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=swx_db
DB_USER=swx_user
DB_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY={secrets.token_urlsafe(32)}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
"""


def _setup_storage_directories():
    """Create storage directories for framework cache and logs."""
    click.secho("\n📁 Setting up storage directories...", fg="cyan")
    
    directories = [
        "storage/framework/cache",
        "storage/framework/sessions",
        "storage/logs",
        "storage/app/public",
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # Create .gitkeep to preserve directory
        gitkeep = os.path.join(directory, ".gitkeep")
        if not os.path.exists(gitkeep):
            Path(gitkeep).touch()
    
    click.secho("✅ Storage directories created", fg="green")


def _setup_plugin_manifest():
    """Create plugin manifest if it doesn't exist."""
    manifest_dir = os.path.dirname(PLUGIN_MANIFEST_FILE)
    os.makedirs(manifest_dir, exist_ok=True)
    
    if not os.path.exists(PLUGIN_MANIFEST_FILE):
        manifest = {
            "plugins": {},
            "enabled": [],
            "version": "1.0.0"
        }
        with open(PLUGIN_MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
        click.secho("✅ Plugin manifest created", fg="green")


def _setup_database():
    """Run database migrations."""
    click.secho("\n🗄️ Setting up database...", fg="cyan")
    
    if not shutil.which("alembic"):
        click.secho("⚠️  Alembic not installed, skipping migrations", fg="yellow")
        return
    
    try:
        # Check if migrations directory exists
        if not os.path.exists("migrations"):
            click.secho("⚠️  No migrations directory found", fg="yellow")
            return
        
        # Run migrations
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            click.secho("✅ Database migrations applied", fg="green")
        else:
            click.secho(f"⚠️  Migration warning: {result.stderr[:100]}", fg="yellow")
    except Exception as e:
        click.secho(f"⚠️  Database setup failed: {str(e)}", fg="yellow")


def _create_superuser():
    """Create interactive superuser."""
    click.secho("\n👤 Create Superuser", fg="cyan")
    
    if not click.confirm("Create a superuser now?", default=True):
        return
    
    email = click.prompt("Superuser email")
    password = click.prompt("Superuser password", hide_input=True, confirmation_prompt=True)
    
    try:
        # Try to import and run the seed script
        from swx_core.database.core import get_engine, AsyncSessionLocal
        from swx_core.models.user import User
        from swx_core.security.hashing import Hasher
        from sqlalchemy import text
        
        async def create_user():
            async with AsyncSessionLocal() as session:
                # Check if user exists
                result = await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": email}
                )
                if result.fetchone():
                    click.secho("⚠️  User with this email already exists", fg="yellow")
                    return
                
                # Create user
                user = User(
                    email=email,
                    hashed_password=Hasher.get_password_hash(password),
                    is_superuser=True,
                    is_active=True,
                )
                session.add(user)
                await session.commit()
                click.secho("✅ Superuser created successfully", fg="green")
        
        asyncio.run(create_user())
    except ImportError:
        click.secho("⚠️  Could not import user model, skipping superuser creation", fg="yellow")
    except Exception as e:
        click.secho(f"⚠️  Superuser creation failed: {str(e)}", fg="yellow")


# ===================== SERVE COMMAND =====================

@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8001, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, default=True, help="Enable auto-reload")
@click.option("--workers", default=1, type=int, help="Number of workers")
def serve(host: str, port: int, reload: bool, workers: int):
    """
    Start the development server.
    
    Uses uvicorn with hot reload for development.
    
    Example:
        swx serve
        swx serve --port 8080
        swx serve --host 127.0.0.1 --port 3000
        swx serve --no-reload
    """
    click.secho(f"\n🚀 Starting SwX Development Server", fg="cyan", bold=True)
    click.secho(f"   Host: {host}", fg="white")
    click.secho(f"   Port: {port}", fg="white")
    click.secho(f"   Reload: {reload}", fg="white")
    click.secho(f"   Workers: {workers}", fg="white")
    click.secho(f"\n   API: http://{host}:{port}/api", fg="green")
    click.secho(f"   Docs: http://{host}:{port}/docs", fg="green")
    click.secho(f"   ReDoc: http://{host}:{port}/redoc", fg="green")
    click.secho("")
    
    # Check for maintenance mode
    if os.path.exists(MAINTENANCE_FILE):
        click.secho("⚠️  Warning: Application is in maintenance mode", fg="yellow")
        if click.confirm("Remove maintenance mode?", default=True):
            os.remove(MAINTENANCE_FILE)
            click.secho("✅ Maintenance mode disabled", fg="green")
    
    try:
        # Import the app
        import uvicorn
        from swx_core.main import app
        
        uvicorn.run(
            "swx_core.main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level="info",
        )
    except ImportError as e:
        click.secho(f"❌ Failed to import app: {e}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"❌ Server error: {e}", fg="red")
        sys.exit(1)


# ===================== MAINTENANCE MODE COMMANDS =====================

@click.command()
@click.option("--message", default="Application is under maintenance. Please try again later.", help="Maintenance message")
def down(message: str):
    """
    Put the application in maintenance mode.
    
    Creates a maintenance file that middleware checks to return 503.
    
    Example:
        swx down
        swx down --message "Upgrading database, back in 5 minutes"
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(MAINTENANCE_FILE), exist_ok=True)
    
    maintenance_data = {
        "message": message,
        "started_at": datetime.now().isoformat(),
    }
    
    with open(MAINTENANCE_FILE, "w") as f:
        json.dump(maintenance_data, f, indent=2)
    
    click.secho("⛔ Application is now in maintenance mode", fg="yellow", bold=True)
    click.secho(f"   Message: {message}", fg="white")
    click.secho(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fg="white")
    click.secho("\nUse 'swx up' to bring the application back online.", fg="cyan")


@click.command()
def up():
    """
    Bring the application out of maintenance mode.
    
    Removes the maintenance file.
    
    Example:
        swx up
    """
    if not os.path.exists(MAINTENANCE_FILE):
        click.secho("✅ Application is already online", fg="green")
        return
    
    try:
        os.remove(MAINTENANCE_FILE)
        click.secho("✅ Application is now online", fg="green", bold=True)
    except Exception as e:
        click.secho(f"❌ Failed to remove maintenance file: {e}", fg="red")
        sys.exit(1)


# ===================== OPTIMIZE COMMAND =====================

@click.command()
@click.option("--routes", is_flag=True, help="Cache routes only")
@click.option("--config", is_flag=True, help="Cache config only")
def optimize(routes: bool, config: bool):
    """
    Cache routes and configuration for production.
    
    Generates cache files for faster application startup.
    
    Example:
        swx optimize
        swx optimize --routes
        swx optimize --config
    """
    click.secho("\n⚡ Optimizing SwX Framework\n", fg="cyan", bold=True)
    
    # Cache both if no specific option
    cache_routes = routes or (not routes and not config)
    cache_config = config or (not routes and not config)
    
    if cache_routes:
        _cache_routes()
    
    if cache_config:
        _cache_config()
    
    click.secho("\n✨ Optimization complete!", fg="green", bold=True)


def _cache_routes():
    """Cache all application routes."""
    click.secho("📦 Caching routes...", fg="cyan")
    
    try:
        from swx_core.main import app
        
        routes_data = []
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                route_info = {
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else [],
                    "name": getattr(route, "name", None),
                }
                routes_data.append(route_info)
        
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(ROUTE_CACHE_FILE), exist_ok=True)
        
        with open(ROUTE_CACHE_FILE, "w") as f:
            json.dump(routes_data, f, indent=2)
        
        click.secho(f"   ✅ Cached {len(routes_data)} routes", fg="green")
    except ImportError:
        click.secho("   ⚠️  Could not import app, skipping route cache", fg="yellow")
    except Exception as e:
        click.secho(f"   ❌ Route cache failed: {e}", fg="red")


def _cache_config():
    """Cache configuration for faster loading."""
    click.secho("📦 Caching configuration...", fg="cyan")
    
    try:
        from swx_core.config.settings import settings
        
        # Get all settings as dict
        config_data = {}
        for key, value in settings.model_dump().items():
            # Skip sensitive values
            if any(sensitive in key.lower() for sensitive in ["password", "secret", "key", "token"]):
                config_data[key] = "***REDACTED***"
            else:
                config_data[key] = value
        
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(CONFIG_CACHE_FILE), exist_ok=True)
        
        with open(CONFIG_CACHE_FILE, "w") as f:
            json.dump(config_data, f, indent=2, default=str)
        
        click.secho(f"   ✅ Cached configuration", fg="green")
    except ImportError:
        click.secho("   ⚠️  Could not import settings, skipping config cache", fg="yellow")
    except Exception as e:
        click.secho(f"   ❌ Config cache failed: {e}", fg="red")


# ===================== ROUTE LIST COMMAND =====================

@click.command("route:list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--path", default=None, help="Filter by path prefix")
@click.option("--method", default=None, help="Filter by HTTP method")
def route_list(as_json: bool, path: Optional[str], method: Optional[str]):
    """
    List all registered routes.
    
    Parses FastAPI routes and displays them in a formatted table.
    
    Example:
        swx route:list
        swx route:list --path /users
        swx route:list --method GET
        swx route:list --json
    """
    try:
        from swx_core.main import app
    except ImportError:
        click.secho("❌ Could not import FastAPI app", fg="red")
        sys.exit(1)
    
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            path_str = route.path
            methods = list(route.methods) if route.methods else []
            name = getattr(route, "name", "")
            
            # Apply filters
            if path and not path_str.startswith(path):
                continue
            if method and method.upper() not in methods:
                continue
            
            routes.append({
                "methods": ", ".join(sorted(methods)),
                "path": path_str,
                "name": name or "-",
            })
    
    if as_json:
        click.echo(json.dumps(routes, indent=2))
        return
    
    if not routes:
        click.secho("No routes found", fg="yellow")
        return
    
    # Print table
    click.secho("\n📋 Registered Routes\n", fg="cyan", bold=True)
    
    # Calculate column widths
    max_methods = max(len(r["methods"]) for r in routes) + 2
    max_path = max(len(r["path"]) for r in routes) + 2
    
    # Header
    header = f"{'Methods':<{max_methods}} {'Path':<{max_path}} {'Name':<20}"
    click.secho(header, fg="cyan", bold=True)
    click.secho("-" * len(header), fg="white")
    
    # Routes
    for route in routes:
        methods_str = route["methods"]
        # Color methods
        method_colors = {
            "GET": "green",
            "POST": "blue",
            "PUT": "yellow",
            "PATCH": "magenta",
            "DELETE": "red",
        }
        
        colored_methods = []
        for m in route["methods"].split(", "):
            color = method_colors.get(m.strip(), "white")
            colored_methods.append(click.style(m, fg=color))
        
        click.echo(f"{'|'.join(colored_methods):<{max_methods}} {route['path']:<{max_path}} {route['name']:<20}")
    
    click.secho(f"\n  Total: {len(routes)} routes", fg="cyan")


# ===================== CONFIG COMMANDS =====================

@click.command("config:cache")
def config_cache():
    """
    Cache configuration for faster loading.
    
    Example:
        swx config:cache
    """
    _cache_config()
    click.secho("\n✅ Configuration cached", fg="green")


@click.command("config:clear")
def config_clear():
    """
    Clear configuration cache.
    
    Example:
        swx config:clear
    """
    if os.path.exists(CONFIG_CACHE_FILE):
        os.remove(CONFIG_CACHE_FILE)
        click.secho("✅ Configuration cache cleared", fg="green")
    else:
        click.secho("No configuration cache to clear", fg="yellow")


# ===================== PUBLISH COMMAND =====================

@click.command()
@click.argument("tag", type=click.Choice(["config", "migrations", "all"]))
@click.option("--force", is_flag=True, help="Overwrite existing files")
def publish(tag: str, force: bool):
    """
    Publish core assets to application directory.
    
    Copies framework configurations or migrations to swx_app.
    
    Example:
        swx publish config
        swx publish migrations
        swx publish all --force
    """
    click.secho(f"\n📦 Publishing {tag}...\n", fg="cyan")
    
    if tag in ("config", "all"):
        _publish_config(force)
    
    if tag in ("migrations", "all"):
        _publish_migrations(force)
    
    click.secho("\n✨ Publish complete!", fg="green", bold=True)


def _publish_config(force: bool):
    """Publish default configuration files."""
    click.secho("📄 Publishing configuration files...", fg="cyan")
    
    # Define config files to publish
    config_files = {
        "swx_core/config/settings.py": "swx_app/config/settings.example.py",
    }
    
    swx_app_config = "swx_app/config"
    os.makedirs(swx_app_config, exist_ok=True)
    
    published = 0
    for src, dest in config_files.items():
        if os.path.exists(dest) and not force:
            click.secho(f"   ⏭️  {dest} already exists (use --force to overwrite)", fg="yellow")
            continue
        
        if not os.path.exists(src):
            click.secho(f"   ⚠️  Source {src} not found", fg="yellow")
            continue
        
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        click.secho(f"   ✅ Published {dest}", fg="green")
        published += 1
    
    click.secho(f"   {published} config file(s) published", fg="cyan")


def _publish_migrations(force: bool):
    """Publish framework migrations."""
    click.secho("📄 Publishing migrations...", fg="cyan")
    
    src_dir = "swx_core/migrations"
    dest_dir = "migrations/published"
    
    if not os.path.exists(src_dir):
        click.secho("   ⚠️  No framework migrations to publish", fg="yellow")
        return
    
    os.makedirs(dest_dir, exist_ok=True)
    
    published = 0
    for filename in os.listdir(src_dir):
        if filename.endswith(".py"):
            src = os.path.join(src_dir, filename)
            dest = os.path.join(dest_dir, filename)
            
            if os.path.exists(dest) and not force:
                click.secho(f"   ⏭️  {filename} already exists", fg="yellow")
                continue
            
            shutil.copy2(src, dest)
            click.secho(f"   ✅ Published {filename}", fg="green")
            published += 1
    
    click.secho(f"   {published} migration(s) published", fg="cyan")


# ===================== PLUGIN COMMANDS =====================

@click.group()
def plugin():
    """
    Plugin management commands.
    
    Manage plugins in swx_app/plugins directory.
    """
    pass


@plugin.command("list")
def plugin_list():
    """
    List all installed plugins.
    
    Example:
        swx plugin:list
    """
    if not os.path.exists(PLUGIN_MANIFEST_FILE):
        click.secho("No plugin manifest found. Run 'swx setup' first.", fg="yellow")
        return
    
    with open(PLUGIN_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    plugins = manifest.get("plugins", {})
    enabled = manifest.get("enabled", [])
    
    if not plugins:
        click.secho("\n📦 No plugins installed\n", fg="cyan")
        return
    
    click.secho("\n📦 Installed Plugins\n", fg="cyan", bold=True)
    
    for name, info in plugins.items():
        status = click.style("enabled", fg="green") if name in enabled else click.style("disabled", fg="red")
        version = info.get("version", "unknown")
        click.echo(f"  {name:<30} {version:<15} [{status}]")
    
    click.secho(f"\n  Total: {len(plugins)} plugins ({len(enabled)} enabled)", fg="cyan")


@plugin.command("enable")
@click.argument("name")
def plugin_enable(name: str):
    """
    Enable a plugin.
    
    Example:
        swx plugin:enable my-plugin
    """
    if not os.path.exists(PLUGIN_MANIFEST_FILE):
        click.secho("No plugin manifest found. Run 'swx setup' first.", fg="yellow")
        return
    
    with open(PLUGIN_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    plugins = manifest.get("plugins", {})
    
    if name not in plugins:
        click.secho(f"❌ Plugin '{name}' not found", fg="red")
        return
    
    if name in manifest.get("enabled", []):
        click.secho(f"✅ Plugin '{name}' is already enabled", fg="green")
        return
    
    manifest["enabled"].append(name)
    
    with open(PLUGIN_MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    
    click.secho(f"✅ Plugin '{name}' enabled", fg="green")


@plugin.command("disable")
@click.argument("name")
def plugin_disable(name: str):
    """
    Disable a plugin.
    
    Example:
        swx plugin:disable my-plugin
    """
    if not os.path.exists(PLUGIN_MANIFEST_FILE):
        click.secho("No plugin manifest found. Run 'swx setup' first.", fg="yellow")
        return
    
    with open(PLUGIN_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    if name not in manifest.get("enabled", []):
        click.secho(f"✅ Plugin '{name}' is already disabled", fg="green")
        return
    
    manifest["enabled"].remove(name)
    
    with open(PLUGIN_MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    
    click.secho(f"✅ Plugin '{name}' disabled", fg="green")


@plugin.command("install")
@click.argument("url")
@click.option("--name", default=None, help="Plugin name (derived from URL if not provided)")
def plugin_install(url: str, name: Optional[str]):
    """
    Install a plugin from a URL.
    
    Downloads and installs a plugin from a Git repository or PyPI.
    
    Example:
        swx plugin:install https://github.com/user/swx-plugin-auth
        swx plugin:install https://github.com/user/swx-plugin-auth --name auth-plugin
    """
    click.secho(f"\n📦 Installing plugin from {url}...\n", fg="cyan")
    
    # Derive plugin name from URL
    if not name:
        name = url.rstrip("/").split("/")[-1]
        # Remove common prefixes/suffixes
        name = name.replace("swx-plugin-", "").replace("swx_", "")
    
    plugin_dir = f"swx_app/plugins/{name}"
    
    if os.path.exists(plugin_dir):
        click.secho(f"❌ Plugin directory already exists: {plugin_dir}", fg="red")
        click.secho("Use --force to overwrite or uninstall first", fg="yellow")
        return
    
    # Try git clone
    if shutil.which("git"):
        click.secho("   Cloning repository...", fg="cyan")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, plugin_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Remove .git directory
            git_dir = os.path.join(plugin_dir, ".git")
            if os.path.exists(git_dir):
                shutil.rmtree(git_dir)
            
            # Update manifest
            _update_plugin_manifest(name, url, "1.0.0")
            
            click.secho(f"\n✅ Plugin '{name}' installed successfully", fg="green")
            return
        else:
            click.secho(f"   ⚠️  Git clone failed: {result.stderr[:100]}", fg="yellow")
    
    # Fallback: try pip install
    if shutil.which("pip"):
        click.secho("   Attempting pip install...", fg="cyan")
        result = subprocess.run(
            ["pip", "install", url],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            _update_plugin_manifest(name, url, "1.0.0")
            click.secho(f"\n✅ Plugin '{name}' installed via pip", fg="green")
            return
    
    click.secho(f"\n❌ Failed to install plugin '{name}'", fg="red")


def _update_plugin_manifest(name: str, url: str, version: str):
    """Update the plugin manifest."""
    if not os.path.exists(PLUGIN_MANIFEST_FILE):
        _setup_plugin_manifest()
    
    with open(PLUGIN_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    manifest["plugins"][name] = {
        "url": url,
        "version": version,
        "installed_at": datetime.now().isoformat(),
    }
    
    if name not in manifest["enabled"]:
        manifest["enabled"].append(name)
    
    with open(PLUGIN_MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


# ===================== UPGRADE COMMAND =====================

@click.command()
@click.option("--version", default=None, help="Target version to upgrade to")
@click.option("--no-migrate", is_flag=True, help="Skip database migrations")
@click.option("--no-deps", is_flag=True, help="Skip dependency updates")
@click.confirmation_option(prompt="Are you sure you want to upgrade?")
def upgrade(version: Optional[str], no_migrate: bool, no_deps: bool):
    """
    Upgrade the SwX framework.
    
    Checks for updates, pulls latest code, and runs migrations.
    
    Example:
        swx upgrade
        swx upgrade --version 2.0.0
        swx upgrade --no-migrate
    """
    click.secho("\n🔄 SwX Framework Upgrade\n", fg="cyan", bold=True)
    
    # Step 1: Check current version
    try:
        from swx_core import __version__
        current_version = __version__
    except ImportError:
        current_version = "unknown"
    
    click.secho(f"   Current version: {current_version}", fg="white")
    
    # Step 2: Check if git repository
    if os.path.exists(".git"):
        click.secho("\n📥 Checking for updates...", fg="cyan")
        
        # Fetch latest
        result = subprocess.run(
            ["git", "fetch", "--dry-run"],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            click.secho("   Updates available!", fg="green")
            
            if click.confirm("Pull latest changes?"):
                result = subprocess.run(
                    ["git", "pull"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    click.secho("   ✅ Pulled latest changes", fg="green")
                else:
                    click.secho(f"   ❌ Pull failed: {result.stderr[:100]}", fg="red")
                    return
        else:
            click.secho("   Already up to date", fg="green")
    else:
        click.secho("   Not a git repository, skipping git operations", fg="yellow")
    
    # Step 3: Update dependencies
    if not no_deps:
        click.secho("\n📦 Updating dependencies...", fg="cyan")
        
        if os.path.exists("requirements.txt"):
            result = subprocess.run(
                ["pip", "install", "-r", "requirements.txt", "--upgrade"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                click.secho("   ✅ Dependencies updated", fg="green")
            else:
                click.secho(f"   ⚠️  Dependency update warning: {result.stderr[:100]}", fg="yellow")
    
    # Step 4: Run migrations
    if not no_migrate:
        click.secho("\n🗄️ Running database migrations...", fg="cyan")
        
        if shutil.which("alembic"):
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                click.secho("   ✅ Migrations applied", fg="green")
            else:
                click.secho(f"   ⚠️  Migration warning: {result.stderr[:100]}", fg="yellow")
        else:
            click.secho("   ⚠️  Alembic not found, skipping migrations", fg="yellow")
    
    # Step 5: Clear cache
    click.secho("\n🗑️ Clearing cache...", fg="cyan")
    
    for cache_file in [ROUTE_CACHE_FILE, CONFIG_CACHE_FILE]:
        if os.path.exists(cache_file):
            os.remove(cache_file)
    
    click.secho("   ✅ Cache cleared", fg="green")
    
    click.secho("\n✨ Upgrade complete! Run 'swx optimize' to rebuild cache.", fg="green", bold=True)


    cli_group.add_command(upgrade, "upgrade")
def register_framework_commands(cli_group):
    """Register all framework commands with the CLI group."""
    cli_group.add_command(setup, "setup")
    cli_group.add_command(serve, "serve")
    cli_group.add_command(down, "down")
    cli_group.add_command(up, "up")
    cli_group.add_command(optimize, "optimize")
    cli_group.add_command(route_list, "route:list")
    cli_group.add_command(config_cache, "config:cache")
    cli_group.add_command(config_clear, "config:clear")
    cli_group.add_command(publish, "publish")
    cli_group.add_command(plugin, "plugin")
    cli_group.add_command(upgrade, "upgrade")
    # Import and register doctor command
    from swx_core.cli.commands.doctor import doctor_command
    cli_group.add_command(doctor_command, "doctor")


# Standalone execution for testing
if __name__ == "__main__":
    @click.group()
    def test_cli():
        pass
    
    register_framework_commands(test_cli)
    test_cli()