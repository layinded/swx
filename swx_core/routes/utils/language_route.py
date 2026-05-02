"""
Language Routes
---------------
This module defines the API routes for managing language resources.

Features:
- Provides endpoints for retrieving, creating, updating, and deleting language records.
- Implements pagination and filtering for optimized queries.
- Enforces admin-level authentication for modification routes.

Routes:
- `GET /utils/language/`: Retrieve all language records.
- `GET /utils/language/bulk`: Retrieve multiple language records in bulk.
- `GET /utils/language/{id}`: Retrieve a single language record by ID.
- `GET /utils/language/code/{language_code}`: Retrieve all records for a given language code.
- `GET /utils/language/{language_code}/{key}`: Retrieve a specific translation by language code and key.
- `POST /utils/language/`: Create a new language record (Admin Only).
- `POST /utils/language/bulk`: Create multiple language records (Admin Only).
- `PUT /utils/language/{id}`: Update an existing language record (Admin Only).
- `DELETE /utils/language/{id}`: Delete an existing language record (Admin Only).
"""

import uuid
from typing import List, Dict, Any

from fastapi import APIRouter, Request, Depends, Query

from swx_core.controllers.language_controller import LanguageController
from swx_core.database.db import SessionDep
from swx_core.models.common import Message
from swx_core.models.language import (
    LanguageCreate,
    LanguageUpdate,
    LanguagePublic,
    LanguageCreateSchema,
    BulkLanguageResponse,
)
from swx_core.auth.admin.dependencies import get_current_admin_user

# Initialize API router with a prefix for language utilities
router = APIRouter(prefix="/utils/language")


@router.get(
    "/",
    response_model=list[LanguagePublic],
    summary="Get all language resources",
    description="Retrieve all language resources with optional pagination.",
)
async def get_all_language(
    request: Request,
    db: SessionDep,
    skip: int = Query(0, description="Number of items to skip."),
    limit: int = Query(100, description="Maximum number of items to return."),
):
    """
    Retrieve all language resources with pagination.

    Args:
        request (Request): The HTTP request object.
        db (SessionDep): Database session dependency.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.

    Returns:
        list[LanguagePublic]: A list of language records.
    """
    return await LanguageController.retrieve_all_language_resources(
        request, db, skip=skip, limit=limit
    )


@router.get(
    "/bulk",
    response_model=dict[str, dict[str, str]],
    summary="Retrieve all language translations in bulk",
    description="Retrieve multiple language translations at once by specifying the required languages.",
)
async def get_language_by_all_bulk(db: SessionDep, languages: list[str] = Query(...)):
    """
    Retrieve translations for multiple languages in bulk.

    Args:
        db (SessionDep): Database session dependency.
        languages (list[str]): List of language codes to retrieve translations for.

    Returns:
        dict: A dictionary where each language code maps to its corresponding translations.
    """
    return await LanguageController.retrieve_all_bulk_language_resources(db, languages)


@router.get(
    "/{id}",
    response_model=LanguagePublic,
    summary="Retrieve language resource by ID",
    description="Fetch a single language resource using its unique identifier.",
)
async def get_language_by_id(request: Request, id: uuid.UUID, db: SessionDep):
    """
    Retrieve a single language resource by its unique ID.

    Args:
        request (Request): The HTTP request object.
        id (uuid.UUID): The unique identifier of the language record.
        db (SessionDep): Database session dependency.

    Returns:
        LanguagePublic: The language record matching the provided ID.
    """
    return await LanguageController.retrieve_language_by_id(request, id, db)


@router.get(
    "/code/{language_code}",
    response_model=list[LanguagePublic],
    summary="Retrieve language resources by language code",
    description="Fetch all language resources that match a given language code.",
)
async def get_language_by_code(request: Request, language_code: str, db: SessionDep):
    """
    Retrieve all language resources for a given language code.

    Args:
        request (Request): The HTTP request object.
        language_code (str): The language code (e.g., "en").
        db (SessionDep): Database session dependency.

    Returns:
        list[LanguagePublic]: A list of language records for the specified language code.
    """
    return await LanguageController.retrieve_by_language_code(request, language_code, db)


@router.get(
    "/{language_code}/{key}",
    response_model=LanguagePublic,
    summary="Retrieve translation by language code and key",
    description="Fetch a single language translation using both language code and key.",
)
async def get_language_by_code_and_key(
    request: Request, language_code: str, key: str, db: SessionDep
):
    """
    Retrieve a specific translation entry by its language code and key.

    Args:
        request (Request): The HTTP request object.
        language_code (str): The language code (e.g., "en").
        key (str): The translation key.
        db (SessionDep): Database session dependency.

    Returns:
        LanguagePublic: The matching language record.
    """
    return await LanguageController.retrieve_language_by_code_and_key(
        request, db, language_code, key
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_admin_user)],
    response_model=LanguagePublic,
    status_code=201,
    summary="Create a new language record (Admin Only)",
    description="Allows an administrator to create a new language translation entry.",
)
async def create(request: Request, data: LanguageCreate, db: SessionDep):
    """
    Create a new language resource.

    Args:
        request (Request): The HTTP request object.
        data (LanguageCreate): The language data to be created.
        db (SessionDep): Database session dependency.

    Returns:
        LanguagePublic: The newly created language record.
    """
    return await LanguageController.create_new_language(request, data, db)


@router.post(
    "/bulk",
    dependencies=[Depends(get_current_admin_user)],
    response_model=Message,
    status_code=201,
    summary="Create multiple language records in bulk (Admin Only)",
    description="Allows an administrator to create multiple language records at once.",
)
async def create_bulk(request: Request, data: list[LanguageCreateSchema], db: SessionDep) -> Any:
    """
    Create multiple language resources in bulk.

    Args:
        request (Request): The HTTP request object.
        data (list[LanguageCreateSchema]): A list of language data to be created.
        db (SessionDep): Database session dependency.

    Returns:
        Message: A response message indicating the operation status.
    """
    return await LanguageController.create_new_bulk_language(request, data, db)


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_admin_user)],
    response_model=LanguagePublic,
    summary="Update an existing language record (Admin Only)",
    description="Allows an administrator to modify an existing language translation.",
)
async def update(request: Request, id: uuid.UUID, data: LanguageUpdate, db: SessionDep):
    """
    Update an existing language resource.

    Args:
        request (Request): The HTTP request object.
        id (uuid.UUID): The unique identifier of the language record.
        data (LanguageUpdate): The updated data.
        db (SessionDep): Database session dependency.

    Returns:
        LanguagePublic: The updated language record.
    """
    return await LanguageController.update_existing_language(request, id, data, db)


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_admin_user)],
    status_code=204,
    summary="Delete a language record (Admin Only)",
    description="Allows an administrator to remove a language record permanently.",
)
async def delete(request: Request, id: uuid.UUID, db: SessionDep):
    """
    Delete an existing language resource.

    Args:
        request (Request): The HTTP request object.
        id (uuid.UUID): The unique identifier of the language record.
        db (SessionDep): Database session dependency.

    Returns:
        None: If the deletion is successful.
    """
    return await LanguageController.delete_existing_language(request, id, db)
