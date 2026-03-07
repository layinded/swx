"""
Language Repository
-------------------
This module provides database interaction methods for managing language resources.

Features:
- Retrieve single or multiple language resources.
- Create, update, and delete language records.
- Support for bulk retrieval of translations.

Methods:
- `retrieve_all_language_resources()`: Fetch all language resources with pagination.
- `retrieve_all_bulk_language_resources()`: Retrieve translations for multiple languages.
- `retrieve_language_by_id()`: Fetch a single language record by its unique ID.
- `retrieve_language_by_code_and_key()`: Fetch a language entry by language code and key.
- `retrieve_by_language_code()`: Fetch all language records by a specific language code.
- `create_new_language()`: Insert a new language record into the database.
- `update_existing_language()`: Modify an existing language record.
- `delete_existing_language()`: Remove a language record from the database.
"""

import uuid
from sqlmodel import select
from swx_core.database.db import SessionDep
from swx_core.models.language import Language, LanguageCreate, LanguageUpdate


from sqlalchemy.ext.asyncio import AsyncSession

class LanguageRepository:
    """
    Database repository for handling language-related operations.

    Provides CRUD (Create, Read, Update, Delete) functionality for language records.
    """

    @staticmethod
    async def retrieve_all_language_resources(
            db: AsyncSession, skip: int = 0, limit: int = 100
    ):
        """
        Retrieve all language resources with pagination.

        Args:
            db (AsyncSession): Database session dependency.
            skip (int): Number of records to skip for pagination.
            limit (int): Maximum number of records to return.

        Returns:
            List[Language]: A list of language records.
        """
        query = select(Language).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def retrieve_all_bulk_language_resources(db: AsyncSession, languages: list[str]):
        """
        Retrieve all language resources for multiple languages in bulk.

        Args:
            db (AsyncSession): Database session dependency.
            languages (list[str]): List of language codes to retrieve translations for.

        Returns:
            dict: A dictionary where the keys are language codes and the values are
                  dictionaries containing translation key-value pairs.
        """
        translations_dict = {}
        for lang in languages:
            translations = await LanguageRepository.retrieve_by_language_code(db, lang)
            # Build a dictionary: key is the translation key, value is its translation value
            translations_dict[lang] = {t.key: t.value for t in translations}
        return translations_dict

    @staticmethod
    async def retrieve_language_by_id(db: AsyncSession, id: uuid.UUID):
        """
        Retrieve a single language resource by its unique ID.

        Args:
            db (AsyncSession): Database session dependency.
            id (uuid.UUID): The unique identifier of the language record.

        Returns:
            Language | None: The matching language record, or None if not found.
        """
        return await db.get(Language, id)

    @staticmethod
    async def retrieve_language_by_code_and_key(db: AsyncSession, language_code: str, key: str):
        """
        Retrieve a single language resource by its language code and translation key.

        Args:
            db (AsyncSession): Database session dependency.
            language_code (str): The language code (e.g., "en").
            key (str): The translation key.

        Returns:
            Language | None: The matching language record, or None if not found.
        """
        query = select(Language).where(
            Language.language_code == language_code, Language.key == key
        )
        result = await db.execute(query)
        return result.scalar_one()

    @staticmethod
    async def retrieve_by_language_code(db: AsyncSession, language_code: str):
        """
        Retrieve all language resources by a given language code.

        Args:
            db (AsyncSession): Database session dependency.
            language_code (str): The language code (e.g., "en", "cs").

        Returns:
            List[Language]: A list of language records for the specified language code.
        """
        query = select(Language).where(Language.language_code == language_code)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def create_new_language(db: AsyncSession, data: LanguageCreate):
        """
        Create a new language resource in the database.

        Args:
            db (AsyncSession): Database session dependency.
            data (LanguageCreate): The data for the new language record.

        Returns:
            Language: The newly created language record.
        """
        obj = Language(**data.model_dump())
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def update_existing_language(db: AsyncSession, id: uuid.UUID, data: LanguageUpdate):
        """
        Update an existing language resource.

        Args:
            db (AsyncSession): Database session dependency.
            id (uuid.UUID): The unique identifier of the language record.
            data (LanguageUpdate): The updated data.

        Returns:
            Language | None: The updated language record, or None if not found.
        """
        obj = await db.get(Language, id)
        if not obj:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await db.commit()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def delete_existing_language(db: AsyncSession, id: uuid.UUID):
        """
        Delete an existing language resource from the database.

        Args:
            db (AsyncSession): Database session dependency.
            id (uuid.UUID): The unique identifier of the language record.

        Returns:
            bool: True if the record was successfully deleted, False if not found.
        """
        obj = await db.get(Language, id)
        if not obj:
            return False
        await db.delete(obj)
        await db.commit()
        return True
