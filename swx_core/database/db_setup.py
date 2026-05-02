"""
Database Setup & Migrations
---------------------------
This script ensures the database is correctly set up by:
1. Checking if the database is ready.
2. Running Alembic migrations to set up schema.
3. Creating the initial superuser.
4. Seeding language translations.

Key Functions:
- `check_db_ready()`: Waits until the database is available.
- `run_alembic_migrations()`: Runs database schema migrations.
- `init_superuser()`: Ensures a superuser exists.
- `seed_languages()`: Adds initial translations from a JSON file.
- `setup_database()`: Runs the full database setup process.
"""

import asyncio
import json
import subprocess
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from swx_core.config.settings import settings
from swx_core.database.db import AsyncSessionLocal, engine
from swx_core.middleware.logging_middleware import logger
from swx_core.models.language import Language
from swx_core.models.admin_user import AdminUser
from swx_core.security.password_security import get_password_hash
from swx_core.models.user import User, UserCreate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource

# Retry settings for ensuring database readiness
max_tries = 60 * 5  # Retries up to 5 minutes
wait_seconds = 1

# Path to the translations JSON file (use importlib.resources for package support)
try:
    from importlib.resources import files
    TRANSLATIONS_FILE = files("swx_core.database").joinpath("languages.json")
except ImportError:
    # Python < 3.9 fallback
    import pkg_resources
    TRANSLATIONS_FILE = pkg_resources.resource_filename("swx_core", "database/languages.json")

@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def check_db_ready() -> None:
    """
    Ensures the database is ready before starting services.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(1))  # Run a simple test query
    except Exception as e:
        logger.error(f"Database is not ready: {e}")
        await alert_engine.emit(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.INFRA,
            event_type="DATABASE_NOT_READY",
            message=f"Database connectivity check failed after multiple retries: {e}",
            metadata={"error": str(e)}
        )
        raise e


def run_alembic_migrations() -> None:
    """
    Runs Alembic migrations to set up the database schema.
    """
    logger.info("Running Alembic migrations...")
    try:
        # Alembic is sync, and this runs once during startup.
        # We run it in a way that it doesn't block the loop if called correctly,
        # but setup_database will be awaited.
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        logger.info("Alembic migrations applied successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Alembic migration failed: {e}")
        # Use sync wrapper for emit if possible, but alert_engine.emit is async.
        # Since this is a sync function, we can't await. 
        # But we can use loop.run_until_complete if we really need to.
        # Or we can just log it here and let the lifespan handle it if it fails there.
        # However, run_alembic_migrations is called from setup_database which IS async.
        raise


async def init_superuser(session: AsyncSession) -> None:
    """
    Ensures a superuser exists in both User and AdminUser domains.
    """
    superuser_email = settings.FIRST_SUPERUSER
    superuser_password = settings.FIRST_SUPERUSER_PASSWORD

    # 1. User Domain Superuser
    statement = select(User).where(User.email == superuser_email)
    result = await session.execute(statement)
    existing_user = result.scalar_one_or_none()
    
    if not existing_user:
        hashed_password = await get_password_hash(superuser_password)
        new_user = User(
            email=superuser_email,
            hashed_password=hashed_password,
            is_superuser=True,
            full_name="System Admin",
        )
        session.add(new_user)
        logger.info(f"User superuser '{superuser_email}' created.")
    else:
        logger.info("User superuser already exists.")

    # 2. Admin Domain Superuser
    statement = select(AdminUser).where(AdminUser.email == superuser_email)
    result = await session.execute(statement)
    existing_admin = result.scalar_one_or_none()
    
    if not existing_admin:
        new_admin = AdminUser(
            email=superuser_email,
            hashed_password=await get_password_hash(superuser_password),
            full_name="System Admin",
        )
        session.add(new_admin)
        logger.info(f"Admin superuser '{superuser_email}' created.")
    else:
        # Update password to ensure it matches settings.py
        existing_admin.hashed_password = await get_password_hash(superuser_password)
        session.add(existing_admin)
        logger.info(f"Admin superuser '{superuser_email}' password updated.")

    await session.commit()


async def seed_languages(session: AsyncSession) -> None:
    """
    Seeds translations from the JSON file into the database.
    """
    logger.info("Seeding languages from JSON file...")
    try:
        # Handle importlib.resources Traversable or regular file path
        if hasattr(TRANSLATIONS_FILE, "read_text"):
            # importlib.resources Traversable (Python >= 3.9)
            content = TRANSLATIONS_FILE.read_text()
            languages = json.loads(content)
        else:
            # Regular file path (Python < 3.9 fallback)
            with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as file:
                languages = json.load(file)

        for lang in languages:
            statement = select(Language).where(
                Language.language_code == lang["language_code"],
                Language.key == lang["key"],
            )
            result = await session.execute(statement)
            existing = result.scalar_one_or_none()
            
            if not existing:
                session.add(Language(**lang))

        await session.commit()
        logger.info("Translations seeded successfully.")
    except FileNotFoundError:
        logger.error(f"Translation file not found.")
    except json.JSONDecodeError:
        logger.error("Error decoding JSON file.")
    except Exception as e:
        logger.error(f"Failed to seed translations: {e}")


async def setup_database() -> None:
    """
    Runs the full database setup process.
    """
    logger.info("Checking database readiness...")
    await check_db_ready()

    # Step 1: Run Alembic migrations (Sync wrapper in async)
    try:
        run_alembic_migrations()
    except Exception as e:
        await alert_engine.emit(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            event_type="MIGRATION_FAILED",
            message=f"Database migration failed during startup: {e}",
            metadata={"error": str(e)}
        )
        raise

    # Step 2: Initialize superuser and seed translations (Async)
    async with AsyncSessionLocal() as session:
        await init_superuser(session)
        await seed_languages(session)

    logger.info("Database is ready and initialized!")


if __name__ == "__main__":
    asyncio.run(setup_database())
