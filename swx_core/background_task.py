"""
Background Task: Translation Cache Refresh
------------------------------------------
This module manages the automatic refresh of the translation cache.

Features:
- Fetches translations from the database.
- Saves updated translations to a cache file.
- Runs periodically in the background.

Functions:
- `refresh_translation_cache()`: Fetches and updates translations every hour.
- `start_cache_refresh()`: Starts the background task in the event loop.
"""

import asyncio
from swx_core.database.db import AsyncSessionLocal
from swx_core.middleware.logging_middleware import logger
from swx_core.services.language_service import LanguageService
from swx_core.utils.language_helper import save_translations_to_cache


async def refresh_translation_cache():
    """
    Periodically refreshes the translation cache by fetching translations from the database.

    Behavior:
        - Runs in an infinite loop.
        - Retrieves all translations from the database.
        - Updates the cache file with new translations.
        - Runs every 1 hour (3600 seconds).

    Logs:
        - Success messages when cache is updated.
        - Warnings if no translations are fetched.
        - Errors if the database query fails.
    """
    languages = ["en", "cs"]  # Add more languages if needed
    while True:
        logger.info("Refreshing translation cache for languages: %s", languages)
        try:
            # Create a new session explicitly from AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                # fetch_all_translations_bulk should return a dict with all translations.
                translations = await LanguageService.retrieve_all_bulk_language_resources(db, languages)
                if translations:
                    save_translations_to_cache(translations)
                    logger.info("Translation cache refreshed successfully. Cache file updated.")
                else:
                    logger.warning("No translations were fetched from the database.")
        except Exception as e:
            logger.error("Error refreshing translation cache: %s", e)

        await asyncio.sleep(3600)  # Wait one hour before refreshing again


def start_cache_refresh():
    """
    Starts the background task for refreshing the translation cache.

    Behavior:
        - Runs `refresh_translation_cache()` as an asyncio background task.
        - Ensures the task is managed properly within the event loop.

    Logs:
        - Info message indicating that the background task has started.
    """
    loop = asyncio.get_event_loop()
    loop.create_task(refresh_translation_cache())
    logger.info("Started translation cache refresh background task.")
