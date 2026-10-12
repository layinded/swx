# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.data_export import DataExportCreate, DataExportUpdate
from swx_core.models.data_import import DataImportCreate, DataImportUpdate
from swx_core.services.data_transfer import data_export_service, data_import_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def export_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "export_type": "user_data",
        "format": "json",
        "status": "pending",
        "file_path": None,
        "file_size": None,
        "record_count": None,
        "error_message": None,
        "expires_at": None,
        "metadata_": None,
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def import_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "import_type": "user_data",
        "format": "json",
        "status": "pending",
        "file_path": None,
        "file_size": None,
        "record_count": None,
        "records_succeeded": None,
        "records_failed": None,
        "error_message": None,
        "metadata_": None,
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


class TestDataExportService:
    async def test_create_export_emits_event(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        body = DataExportCreate(export_type="user_data", format="json")
        stored = export_object(user_id=user_id)
        with patch.object(data_export_service.data_transfer_repository, "create_export", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_export_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await data_export_service.create_export(session, user_id, body)
        assert result.export_type == "user_data"
        assert mock_dispatch.await_args.args[0] == "data_transfer.export_created"

    async def test_get_export_raises_for_missing(self):
        session = AsyncMock()
        export_id = uuid.uuid4()
        with patch.object(data_export_service.data_transfer_repository, "get_export_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await data_export_service.get_export(session, export_id)

    async def test_get_export_raises_permission_error_for_wrong_user(self):
        session = AsyncMock()
        export_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        stored = export_object(id=export_id, user_id=owner_id)
        with patch.object(data_export_service.data_transfer_repository, "get_export_by_id", new_callable=AsyncMock, return_value=stored):
            with pytest.raises(PermissionError, match="access denied"):
                await data_export_service.get_export(session, export_id, user_id=other_id)

    async def test_update_export_emits_event(self):
        session = AsyncMock()
        export_id = uuid.uuid4()
        stored = export_object(id=export_id)
        updated = export_object(id=export_id, status="processing")
        body = DataExportUpdate(status="processing")
        with patch.object(data_export_service.data_transfer_repository, "get_export_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_export_service.data_transfer_repository, "update_export", new_callable=AsyncMock, return_value=updated):
                with patch.object(data_export_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await data_export_service.update_export(session, export_id, body)
        assert result.status == "processing"
        assert mock_dispatch.await_args.args[0] == "data_transfer.export_updated"

    async def test_cancel_export_emits_event(self):
        session = AsyncMock()
        export_id = uuid.uuid4()
        stored = export_object(id=export_id, status="pending")
        cancelled = export_object(id=export_id, status="cancelled")
        with patch.object(data_export_service.data_transfer_repository, "get_export_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_export_service.data_transfer_repository, "update_export", new_callable=AsyncMock, return_value=cancelled):
                with patch.object(data_export_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await data_export_service.cancel_export(session, export_id)
        assert result.status == "cancelled"
        assert mock_dispatch.await_args.args[0] == "data_transfer.export_cancelled"


class TestDataImportService:
    async def test_create_import_emits_event(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        body = DataImportCreate(import_type="user_data")
        stored = import_object(user_id=user_id)
        with patch.object(data_import_service.data_transfer_repository, "create_import", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_import_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await data_import_service.create_import(session, user_id, body)
        assert result.import_type == "user_data"
        assert mock_dispatch.await_args.args[0] == "data_transfer.import_created"

    async def test_get_import_raises_for_missing(self):
        session = AsyncMock()
        import_id = uuid.uuid4()
        with patch.object(data_import_service.data_transfer_repository, "get_import_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await data_import_service.get_import(session, import_id)

    async def test_get_import_raises_permission_error_for_wrong_user(self):
        session = AsyncMock()
        import_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        stored = import_object(id=import_id, user_id=owner_id)
        with patch.object(data_import_service.data_transfer_repository, "get_import_by_id", new_callable=AsyncMock, return_value=stored):
            with pytest.raises(PermissionError, match="access denied"):
                await data_import_service.get_import(session, import_id, user_id=other_id)

    async def test_update_import_emits_event(self):
        session = AsyncMock()
        import_id = uuid.uuid4()
        stored = import_object(id=import_id)
        updated = import_object(id=import_id, status="processing")
        body = DataImportUpdate(status="processing")
        with patch.object(data_import_service.data_transfer_repository, "get_import_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_import_service.data_transfer_repository, "update_import", new_callable=AsyncMock, return_value=updated):
                with patch.object(data_import_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await data_import_service.update_import(session, import_id, body)
        assert result.status == "processing"
        assert mock_dispatch.await_args.args[0] == "data_transfer.import_updated"

    async def test_cancel_import_emits_event(self):
        session = AsyncMock()
        import_id = uuid.uuid4()
        stored = import_object(id=import_id, status="pending")
        cancelled = import_object(id=import_id, status="cancelled")
        with patch.object(data_import_service.data_transfer_repository, "get_import_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(data_import_service.data_transfer_repository, "update_import", new_callable=AsyncMock, return_value=cancelled):
                with patch.object(data_import_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await data_import_service.cancel_import(session, import_id)
        assert result.status == "cancelled"
        assert mock_dispatch.await_args.args[0] == "data_transfer.import_cancelled"