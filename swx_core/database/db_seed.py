"""
Database Seeding Script
------------------------
This script populates the database with initial data, including:
- Superuser creation
- Language translations

Usage:
    Run this script to seed initial data into the database.

Safety Checks:
- Prevents execution in production unless explicitly allowed.

Functions:
- `seed_data()`: Runs database seeding tasks.
- `main()`: Entry point with environment safety check.
"""

import asyncio
import sys

from swx_core.config.settings import settings
from swx_core.database.db import AsyncSessionLocal
from swx_core.database.db_setup import init_superuser, seed_languages
from swx_core.middleware.logging_middleware import logger

async def seed_data() -> None:
    """
    Seeds initial data into the database, such as the superuser and translations.
    Logs errors if seeding fails.
    """
    try:
        async with AsyncSessionLocal() as session:
            logger.info("Starting database seeding...")
            await init_superuser(session)
            await seed_languages(session)
            # await session.commit()  # commit is already handled in init_superuser and seed_languages
        logger.info("Initial data successfully created.")
    except Exception as e:
        logger.error(f"Database seeding failed: {e}", exc_info=True)
        print(f"Seeding failed due to: {e}")
        sys.exit(1)


async def main_async() -> None:
    """
    Entry point for database seeding.

    Checks the environment before running to prevent accidental seeding in production.
    """
    if settings.ENVIRONMENT == "production":
        logger.warning("Seeding data in production is disabled for safety!")
        return

    logger.info("Seeding initial data...")
    await seed_data()

def main() -> None:
    try:
        asyncio.run(main_async())
    except RuntimeError:
        # If loop is already running, create a task (though usually this shouldn't happen here)
        asyncio.create_task(main_async())

if __name__ == "__main__":
    main()
