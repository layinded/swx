"""
Language Controller
-------------------
This module handles API-level operations for managing language resources.

Features:
- Acts as an interface between API requests and the service layer.
- Implements validation and error handling for database interactions.
- Supports bulk operations for efficiency.

Methods:
- `retrieve_all_language_resources()`: Fetch all language resources.
- `retrieve_all_bulk_language_resources()`: Retrieve translations for multiple languages.
- `retrieve_language_by_id()`: Fetch a single language resource by its unique ID.
- `retrieve_by_language_code()`: Fetch all translations for a specific language.
- `retrieve_language_by_code_and_key()`: Fetch a specific translation key-value pair.
- `create_new_language()`: Insert a new language record.
- `create_new_bulk_language()`: Insert multiple language records at once.
- `update_existing_language()`: Modify an existing language record.
- `delete_existing_language()`: Remove a language record.
"""

from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, Request

from swx_core.services.language_service import LanguageService
from swx_core.models.language import (
    LanguageCreate,
    LanguageUpdate,
    LanguagePublic,
    LanguageCreateSchema,
)
from swx_core.middleware.logging_middleware import logger
from swx_core.utils.language_helper import translate


class LanguageController:
    """
    Controller for handling API requests related to language resources.

    Acts as an intermediary between API routes and the service layer.
    Implements request validation, exception handling, and error logging.
    """

    @staticmethod
    async def retrieve_all_language_resources(
        request: Request, db: AsyncSession, skip: int = 0, limit: int = 100
    ):
        """
        Retrieve all language resources with pagination.

        Args:
            request (Request): The HTTP request object.
            db (AsyncSession): Database session dependency.
            skip (int): Number of records to skip for pagination.
            limit (int): Maximum number of records to return.

        Returns:
            List[Language]: A list of language records.

        Raises:
            HTTPException: Returns status 500 if an internal error occurs.
        """
        try:
            return await LanguageService.retrieve_all_language_resources(
                db, skip=skip, limit=limit
            )
        except Exception as e:
            logger.error("Error in retrieve_all_language_resources: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def retrieve_all_bulk_language_resources(db: AsyncSession, languages: list[str]):
        """
        Retrieve translations for multiple languages in bulk.

        Args:
            db (AsyncSession): Database session dependency.
            languages (list[str]): List of language codes to retrieve translations for.

        Returns:
            dict: A dictionary of translations for each language.

        Raises:
            HTTPException: Returns status 500 if an internal error occurs.
        """
        try:
            return await LanguageService.retrieve_all_bulk_language_resources(db, languages)
        except Exception as e:
            logger.error("Error in retrieve_all_language_resources: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def retrieve_language_by_id(request: Request, id: uuid.UUID, db: AsyncSession):
        """
        Retrieve a single language resource by its unique ID.

        Args:
            request (Request): The HTTP request object.
            id (uuid.UUID): The unique identifier of the language record.
            db (AsyncSession): Database session dependency.

        Returns:
            Language: The matching language record.

        Raises:
            HTTPException: Returns status 404 if the record is not found.
        """
        item = await LanguageService.retrieve_language_by_id(db, id)
        if not item:
            raise HTTPException(
                status_code=404, detail=translate(request, f"language.not_found")
            )
        return item

    @staticmethod
    async def retrieve_by_language_code(request: Request, language_code: str, db: AsyncSession):
        """
        Retrieve all translations for a given language code.

        Args:
            request (Request): The HTTP request object.
            language_code (str): The language code (e.g., "en").
            db (AsyncSession): Database session dependency.

        Returns:
            List[Language]: A list of translations for the specified language.

        Raises:
            HTTPException: Returns status 404 if no records are found.
        """
        item = await LanguageService.retrieve_by_language_code(db, language_code)
        if not item:
            raise HTTPException(
                status_code=404, detail=translate(request, f"language.not_found")
            )
        return item

    @staticmethod
    async def retrieve_language_by_code_and_key(
        request: Request, db: AsyncSession, language_code: str, language_key: str
    ):
        """
        Retrieve a single translation entry by its language code and key.

        Args:
            request (Request): The HTTP request object.
            db (AsyncSession): Database session dependency.
            language_code (str): The language code (e.g., "en").
            language_key (str): The translation key.

        Returns:
            Language: The matching language record.

        Raises:
            HTTPException: Returns status 404 if no record is found.
        """
        item = await LanguageService.retrieve_language_by_code_and_key(
            db, language_code, language_key
        )
        if not item:
            raise HTTPException(
                status_code=404, detail=translate(request, f"language.not_found")
            )
        return item

    @staticmethod
    async def create_new_language(request: Request, data: LanguageCreate, db: AsyncSession):
        """
        Create a new language resource.

        Args:
            request (Request): The HTTP request object.
            data (LanguageCreate): The new language data.
            db (AsyncSession): Database session dependency.

        Returns:
            Language: The newly created language record.

        Raises:
            HTTPException: Returns status 500 if an internal error occurs.
        """
        try:
            return await LanguageService.create_new_language(db, data)
        except Exception as e:
            logger.error("Error in create_new_language: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def create_new_bulk_language(request: Request, data: list[LanguageCreateSchema], db: AsyncSession):
        """
        Create multiple language resources in bulk.

        Args:
            request (Request): The HTTP request object.
            data (list[LanguageCreateSchema]): A list of language data.
            db (AsyncSession): Database session dependency.

        Returns:
            dict: A success message.

        Raises:
            HTTPException: Returns status 500 if an internal error occurs.
        """
        try:
            for item in data:
                await LanguageService.create_new_language(db, LanguageCreate(**item.model_dump()))
            return {"message": "Bulk languages created successfully"}
        except Exception as e:
            logger.error("Error in create_new_bulk_language: %s", e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def update_existing_language(
        request: Request, id: uuid.UUID, data: LanguageUpdate, db: AsyncSession
    ):
        """
        Update an existing language resource.

        Args:
            request (Request): The HTTP request object.
            id (uuid.UUID): The unique identifier of the language record.
            data (LanguageUpdate): The updated data.
            db (AsyncSession): Database session dependency.

        Returns:
            Language: The updated language record.

        Raises:
            HTTPException: Returns status 404 if the record is not found.
        """
        item = await LanguageService.update_existing_language(db, id, data)
        if not item:
            raise HTTPException(
                status_code=404, detail=translate(request, f"language.not_found")
            )
        return item

    @staticmethod
    async def delete_existing_language(request: Request, id: uuid.UUID, db: AsyncSession):
        """
        Delete an existing language resource.

        Args:
            request (Request): The HTTP request object.
            id (uuid.UUID): The unique identifier of the language record.
            db (AsyncSession): Database session dependency.

        Returns:
            None: If the deletion is successful.

        Raises:
            HTTPException: Returns status 404 if the record is not found.
        """
        success = await LanguageService.delete_existing_language(db, id)
        if not success:
            raise HTTPException(
                status_code=404, detail=translate(request, f"language.not_found")
            )
        return None
