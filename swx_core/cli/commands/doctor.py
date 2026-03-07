"""
SwX Doctor Command - System Diagnostics and Health Check.

Usage:
    swx doctor           # Run diagnostics
    swx doctor --fix     # Attempt automatic fixes
    swx doctor -v        # Verbose output
    swx doctor --json    # JSON output
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any

import click


@click.command("doctor")
@click.option("--fix", is_flag=True, help="Attempt to fix detected issues")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed diagnostics")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def doctor_command(fix: bool, verbose: bool, json_output: bool):
    """
    System diagnostics and health check.
    
    Checks:
    - Environment configuration
    - Database connectivity
    - Redis connectivity
    - Storage permissions
    - Security settings
    - Dependency versions
    
    Exit Codes:
    - 0: Healthy (all checks passed)
    - 1: Unhealthy (errors detected)
    - 2: Degraded (warnings detected)
    """
    results = {
        "status": "healthy",
        "checks": {},
        "warnings": [],
        "errors": [],
        "fixes_applied": []
    }
    
    click.secho("\n🔍 SwX Framework Diagnostics\n", fg="cyan", bold=True)
    
    # Environment Check
    click.secho("📋 Environment Configuration", fg="cyan")
    env_checks = _check_environment()
    results["checks"]["environment"] = env_checks
    _print_checks(env_checks, results)
    
    # Database Check
    click.secho("\n🗄️  Database Connectivity", fg="cyan")
    db_checks = _check_database(verbose)
    results["checks"]["database"] = db_checks
    _print_checks(db_checks, results)
    
    # Redis Check
    click.secho("\n📦 Redis Connectivity", fg="cyan")
    redis_checks = _check_redis(verbose)
    results["checks"]["redis"] = redis_checks
    _print_checks(redis_checks, results)
    
    # Storage Check
    click.secho("\n📂 Storage Permissions", fg="cyan")
    storage_checks = _check_storage(fix)
    results["checks"]["storage"] = storage_checks
    for check, status in storage_checks.items():
        if status["status"] == "ok":
            click.secho(f"   ✅ {check}", fg="green")
        elif status["status"] == "fixed":
            click.secho(f"   🔧 {check}: Fixed", fg="yellow")
            results["fixes_applied"].append(check)
        else:
            click.secho(f"   ❌ {check}: {status.get('message', '')}", fg="red")
            results["errors"].append(f"{check}: {status.get('message', '')}")
    
    # Security Check
    click.secho("\n🔒 Security Settings", fg="cyan")
    security_checks = _check_security(verbose, fix)
    results["checks"]["security"] = security_checks
    _print_checks(security_checks, results)
    
    # Dependency Check
    click.secho("\n📚 Dependency Status", fg="cyan")
    dep_checks = _check_dependencies()
    results["checks"]["dependencies"] = dep_checks
    for check, status in dep_checks.items():
        if status["status"] == "ok":
            version = status.get("version", "installed")
            click.secho(f"   ✅ {check}: {version}", fg="green")
        elif status["status"] == "warning":
            click.secho(f"   ⚠️  {check}: {status.get('message', '')}", fg="yellow")
            results["warnings"].append(f"{check}: {status.get('message', '')}")
        else:
            click.secho(f"   ❌ {check}: {status.get('message', 'not installed')}", fg="red")
            results["errors"].append(f"{check}: {status.get('message', 'not installed')}")
    
    # Update overall status
    if results["errors"]:
        results["status"] = "unhealthy"
    elif results["warnings"]:
        results["status"] = "degraded"
    
    # Print summary
    click.secho("\n" + "=" * 50, fg="cyan")
    if results["status"] == "healthy":
        click.secho("✅ All checks passed, system is healthy!", fg="green", bold=True)
    elif results["status"] == "degraded":
        click.secho(f"⚠️  System is degraded ({len(results['warnings'])} warnings)", fg="yellow", bold=True)
    else:
        click.secho(f"❌ System is unhealthy ({len(results['errors'])} errors, {len(results['warnings'])} warnings)", fg="red", bold=True)
    
    if results["fixes_applied"]:
        click.secho(f"\n🔧 Fixes applied: {', '.join(results['fixes_applied'])}", fg="green")
    
    if json_output:
        click.echo(json.dumps(results, indent=2, default=str))
        return
    
    # Exit with appropriate code
    if results["status"] == "unhealthy":
        sys.exit(1)
    elif results["status"] == "degraded":
        sys.exit(2)


def _print_checks(checks: Dict, results: Dict):
    """Print check results and update results dict."""
    for check, status in checks.items():
        if status["status"] == "ok":
            if status.get("value"):
                click.secho(f"   ✅ {check}: {status['value']}", fg="green")
            else:
                click.secho(f"   ✅ {check}", fg="green")
        elif status["status"] == "warning":
            click.secho(f"   ⚠️  {check}: {status.get('message', '')}", fg="yellow")
            results["warnings"].append(f"{check}: {status.get('message', '')}")
        else:
            click.secho(f"   ❌ {check}: {status.get('message', '')}", fg="red")
            results["errors"].append(f"{check}: {status.get('message', '')}")


def _check_environment() -> Dict[str, Dict]:
    """Check environment configuration."""
    checks = {}
    
    # Check .env file
    if os.path.exists(".env"):
        checks[".env file"] = {"status": "ok"}
        
        # Parse .env file
        env_vars = {}
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip('"').strip("'")
        
        # Check SECRET_KEY
        secret_key = env_vars.get("SECRET_KEY", "")
        if secret_key:
            if len(secret_key) < 32:
                checks["SECRET_KEY strength"] = {"status": "warning", "message": f"{len(secret_key)} chars (need 32+)"}
            else:
                checks["SECRET_KEY strength"] = {"status": "ok"}
        else:
            checks["SECRET_KEY strength"] = {"status": "error", "message": "not set"}
        
        # Check ENVIRONMENT
        env = env_vars.get("ENVIRONMENT", "").lower()
        if env:
            checks["ENVIRONMENT"] = {"status": "ok", "value": env}
        else:
            checks["ENVIRONMENT"] = {"status": "warning", "message": "not set"}
        
        # Check DATABASE_URL
        if env_vars.get("DATABASE_URL"):
            checks["Database URL"] = {"status": "ok"}
        else:
            checks["Database URL"] = {"status": "warning", "message": "not set"}
    else:
        checks[".env file"] = {"status": "error", "message": "not found"}
    
    # Check Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        checks["Python version"] = {"status": "ok", "value": py_version}
    else:
        checks["Python version"] = {"status": "error", "message": f"{py_version} (need 3.10+)"}
    
    return checks


def _check_database(verbose: bool) -> Dict[str, Dict]:
    """Check database connectivity."""
    checks = {}
    
    try:
        import asyncio
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        
        try:
            from swx_core.config.settings import settings
            db_url = str(settings.DATABASE_URL)
        except Exception:
            db_url = os.environ.get("DATABASE_URL", "")
        
        if not db_url:
            checks["Database URL"] = {"status": "warning", "message": "not configured"}
            return checks
        
        async def check_db():
            try:
                engine = create_async_engine(db_url)
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await engine.dispose()
                return True, None
            except Exception as e:
                return False, str(e)
        
        success, error = asyncio.run(check_db())
        
        if success:
            checks["Connection"] = {"status": "ok"}
            if os.path.exists("migrations"):
                checks["Migrations folder"] = {"status": "ok"}
            if shutil.which("alembic"):
                checks["Alembic CLI"] = {"status": "ok"}
        else:
            msg = error[:200] if verbose else "connection failed"
            checks["Connection"] = {"status": "error", "message": msg}
    
    except ImportError as e:
        checks["SQLAlchemy"] = {"status": "error", "message": "not installed"}
    except Exception as e:
        checks["Database"] = {"status": "error", "message": str(e)[:100]}
    
    return checks


def _check_redis(verbose: bool) -> Dict[str, Dict]:
    """Check Redis connectivity."""
    checks = {}
    
    try:
        import asyncio
        
        try:
            import redis.asyncio as redis
        except ImportError:
            import aioredis as redis
        
        try:
            from swx_core.config.settings import settings
            redis_url = getattr(settings, "REDIS_URL", None)
        except Exception:
            redis_url = os.environ.get("REDIS_URL", "")
        
        if not redis_url:
            checks["Redis URL"] = {"status": "warning", "message": "not configured"}
            return checks
        
        async def check_redis():
            try:
                client = redis.from_url(str(redis_url))
                await client.ping()
                await client.close()
                return True, None
            except Exception as e:
                return False, str(e)
        
        success, error = asyncio.run(check_redis())
        
        if success:
            checks["Connection"] = {"status": "ok"}
        else:
            msg = error[:200] if verbose else "not reachable"
            checks["Connection"] = {"status": "warning", "message": msg}
    
    except ImportError:
        checks["Redis library"] = {"status": "warning", "message": "not installed"}
    except Exception as e:
        checks["Redis"] = {"status": "warning", "message": str(e)[:100]}
    
    return checks


def _check_storage(fix: bool) -> Dict[str, Dict]:
    """Check storage directories and permissions."""
    checks = {}
    
    dirs = [
        "storage",
        "storage/framework",
        "storage/framework/cache",
        "storage/logs",
        "storage/app",
    ]
    
    for dir_path in dirs:
        path = Path(dir_path)
        if path.exists():
            if os.access(dir_path, os.W_OK):
                checks[dir_path] = {"status": "ok"}
            else:
                if fix:
                    try:
                        os.chmod(dir_path, 0o755)
                        checks[dir_path] = {"status": "fixed"}
                    except Exception:
                        checks[dir_path] = {"status": "error", "message": "permission denied"}
                else:
                    checks[dir_path] = {"status": "error", "message": "not writable"}
        else:
            if fix:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    os.chmod(dir_path, 0o755)
                    checks[dir_path] = {"status": "fixed"}
                except Exception as e:
                    checks[dir_path] = {"status": "error", "message": str(e)[:50]}
            else:
                checks[dir_path] = {"status": "error", "message": "not found"}
    
    return checks


def _check_security(verbose: bool, fix: bool) -> Dict[str, Dict]:
    """Check security settings."""
    checks = {}
    
    try:
        from swx_core.config.settings import settings
    except Exception:
        checks["Settings"] = {"status": "error", "message": "cannot load settings"}
        return checks
    
    # Check SECRET_KEY strength
    try:
        secret = str(settings.SECRET_KEY)
        if len(secret) < 32:
            checks["SECRET_KEY length"] = {"status": "warning", "message": f"{len(secret)} chars (need 32+)"}
        else:
            checks["SECRET_KEY length"] = {"status": "ok"}
        
        # Check for weak keys
        weak_patterns = ["secret", "password", "dev", "test", "changeme", "example"]
        if any(p in secret.lower() for p in weak_patterns):
            checks["SECRET_KEY entropy"] = {"status": "warning", "message": "appears to contain weak patterns"}
        else:
            checks["SECRET_KEY entropy"] = {"status": "ok"}
    except Exception as e:
        checks["SECRET_KEY"] = {"status": "error", "message": str(e)[:50]}
    
    # Check environment mode
    try:
        env = str(settings.ENVIRONMENT).lower()
        if env == "production":
            checks["Environment mode"] = {"status": "ok", "value": "production"}
            
            # Production-specific checks
            if "dev" in secret.lower() or "test" in secret.lower():
                checks["Production secret"] = {"status": "error", "message": "using dev/test secret in production"}
            else:
                checks["Production secret"] = {"status": "ok"}
        else:
            checks["Environment mode"] = {"status": "warning", "message": f"{env} (not production)"}
    except Exception:
        checks["Environment mode"] = {"status": "warning", "message": "not set"}
    
    # Check DEBUG mode
    try:
        debug = getattr(settings, "DEBUG", False)
        env = str(getattr(settings, "ENVIRONMENT", "")).lower()
        if debug and env == "production":
            checks["DEBUG mode"] = {"status": "error", "message": "enabled in production!"}
        else:
            checks["DEBUG mode"] = {"status": "ok", "value": str(debug)}
    except Exception:
        pass
    
    # Check CORS
    try:
        cors_origins = getattr(settings, "BACKEND_CORS_ORIGINS", [])
        if cors_origins and "*" not in str(cors_origins):
            checks["CORS origins"] = {"status": "ok"}
        else:
            checks["CORS origins"] = {"status": "warning", "message": "allowing all origins (*)"}
    except Exception:
        pass
    
    # Check token blacklist
    try:
        redis_enabled = getattr(settings, "REDIS_ENABLED", False)
        if redis_enabled:
            checks["Token blacklist"] = {"status": "ok", "value": "Redis enabled"}
        else:
            checks["Token blacklist"] = {"status": "warning", "message": "Redis not enabled"}
    except Exception:
        pass
    
    return checks


def _check_dependencies() -> Dict[str, Dict]:
    """Check installed dependencies."""
    checks = {}
    
    required = [
        ("fastapi", "0.100.0"),
        ("sqlalchemy", "2.0.0"),
        ("sqlmodel", "0.0.21"),
        ("pydantic", "2.0.0"),
        ("pydantic_settings", "2.0.0"),
        ("pyjwt", "2.8.0"),
        ("redis", "5.0.0"),
        ("celery", "5.3.0"),
        ("alembic", "1.12.0"),
        ("uvicorn", "0.23.0"),
    ]
    
    for package, _ in required:
        try:
            mod_name = package.replace("-", "_").split("[")[0]
            mod = __import__(mod_name)
            version = getattr(mod, "__version__", "installed")
            checks[package] = {"status": "ok", "version": str(version)}
        except ImportError:
            checks[package] = {"status": "error", "message": "not installed"}
    
    return checks


def register_doctor_command(cli_group):
    """Register doctor command with CLI group."""
    cli_group.add_command(doctor_command)