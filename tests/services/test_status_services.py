# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from swx_core.models.service_component import ServiceComponentCreate, ServiceComponentUpdate
from swx_core.models.status_incident import StatusIncidentCreate, StatusIncidentUpdate
from swx_core.models.incident_update import IncidentUpdateCreate
from swx_core.services.status import status_component_service, status_incident_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def component_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "API Server",
        "description": "Main API server",
        "group_name": "core",
        "sort_order": 0,
        "status": "operational",
        "uptime_percentage": None,
        "metadata_": None,
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def incident_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "title": "Service Disruption",
        "description": "Users experiencing errors",
        "severity": "major",
        "status": "investigating",
        "component_id": uuid.uuid4(),
        "started_at": now(),
        "resolved_at": None,
        "created_by": uuid.uuid4(),
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def incident_update_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "incident_id": uuid.uuid4(),
        "status": "investigating",
        "message": "Investigating the issue",
        "created_by": uuid.uuid4(),
        "created_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data)


class TestStatusComponentService:
    async def test_create_component_emits_event(self):
        session = AsyncMock()
        body = ServiceComponentCreate(name="API Server", description="Main API", group="core")
        stored = component_object()
        with patch.object(status_component_service.status_repository, "create_component", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_component_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await status_component_service.create_component(session, body)
        assert result.name == "API Server"
        assert mock_dispatch.await_args.args[0] == "status.component_created"

    async def test_get_component_raises_for_missing(self):
        session = AsyncMock()
        component_id = uuid.uuid4()
        with patch.object(status_component_service.status_repository, "get_component_by_id", new_callable=AsyncMock, return_value=None):
            try:
                await status_component_service.get_component(session, component_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert "not found" in str(e)

    async def test_update_component_emits_event(self):
        session = AsyncMock()
        component_id = uuid.uuid4()
        stored = component_object(id=component_id)
        updated = component_object(id=component_id, status="degraded")
        body = ServiceComponentUpdate(status="degraded")
        with patch.object(status_component_service.status_repository, "get_component_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_component_service.status_repository, "update_component", new_callable=AsyncMock, return_value=updated):
                with patch.object(status_component_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await status_component_service.update_component(session, component_id, body)
        assert result.status == "degraded"
        assert mock_dispatch.await_args.args[0] == "status.component_updated"

    async def test_delete_component_emits_event(self):
        session = AsyncMock()
        component_id = uuid.uuid4()
        stored = component_object(id=component_id)
        with patch.object(status_component_service.status_repository, "get_component_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_component_service.status_repository, "delete_component", new_callable=AsyncMock, return_value=stored):
                with patch.object(status_component_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await status_component_service.delete_component(session, component_id)
        assert mock_dispatch.await_args.args[0] == "status.component_deleted"


class TestStatusIncidentService:
    async def test_create_incident_emits_event_and_sets_started_at(self):
        session = AsyncMock()
        admin_id = uuid.uuid4()
        body = StatusIncidentCreate(title="Outage", description="API down", severity="major", component_id=uuid.uuid4())
        stored = incident_object(created_by=admin_id)
        with patch.object(status_incident_service.status_repository, "create_incident", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_incident_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await status_incident_service.create_incident(session, admin_id, body)
        assert mock_dispatch.await_args.args[0] == "status.incident_created"

    async def test_get_incident_raises_for_missing(self):
        session = AsyncMock()
        incident_id = uuid.uuid4()
        with patch.object(status_incident_service.status_repository, "get_incident_by_id", new_callable=AsyncMock, return_value=None):
            try:
                await status_incident_service.get_incident(session, incident_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert "not found" in str(e)

    async def test_update_incident_emits_event(self):
        session = AsyncMock()
        incident_id = uuid.uuid4()
        stored = incident_object(id=incident_id)
        updated = incident_object(id=incident_id, status="identified")
        body = StatusIncidentUpdate(status="identified")
        with patch.object(status_incident_service.status_repository, "get_incident_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_incident_service.status_repository, "update_incident", new_callable=AsyncMock, return_value=updated):
                with patch.object(status_incident_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await status_incident_service.update_incident(session, incident_id, body)
        assert result.status == "identified"
        assert mock_dispatch.await_args.args[0] == "status.incident_updated"

    async def test_resolve_incident_emits_event(self):
        session = AsyncMock()
        incident_id = uuid.uuid4()
        stored = incident_object(id=incident_id)
        resolved = incident_object(id=incident_id, status="resolved")
        with patch.object(status_incident_service.status_repository, "get_incident_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_incident_service.status_repository, "update_incident", new_callable=AsyncMock, return_value=resolved):
                with patch.object(status_incident_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await status_incident_service.resolve_incident(session, incident_id)
        assert result.status == "resolved"
        assert mock_dispatch.await_args.args[0] == "status.incident_resolved"

    async def test_add_incident_update_emits_event(self):
        session = AsyncMock()
        incident_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        stored = incident_object(id=incident_id)
        update_obj = incident_update_object(incident_id=incident_id, created_by=admin_id)
        body = IncidentUpdateCreate(status="investigating", message="Looking into it")
        with patch.object(status_incident_service.status_repository, "get_incident_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(status_incident_service.status_repository, "create_incident_update", new_callable=AsyncMock, return_value=update_obj):
                with patch.object(status_incident_service.status_repository, "update_incident", new_callable=AsyncMock):
                    with patch.object(status_incident_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await status_incident_service.add_incident_update(session, incident_id, admin_id, body)
        assert mock_dispatch.await_args.args[0] == "status.incident_update_added"

    async def test_get_status_summary(self):
        session = AsyncMock()
        comp = component_object()
        incident = incident_object(status="investigating")
        with patch.object(status_incident_service.status_repository, "list_components", new_callable=AsyncMock, return_value=[comp]):
            with patch.object(status_incident_service.status_repository, "get_active_incidents", new_callable=AsyncMock, return_value=[incident]):
                result = await status_incident_service.get_status_summary(session)
        assert "components" in result
        assert "active_incidents" in result