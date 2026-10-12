import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from swx_core.events import event_bus
from swx_core.models.organization import OrganizationCreate, OrganizationRole, OrganizationUpdate


class TestOrganizationEvents:
    async def test_create_update_delete_emit_events(self):
        from swx_core.services import organization_service

        session = AsyncMock()
        owner_id = uuid.uuid4()
        org_id = uuid.uuid4()
        created = SimpleNamespace(id=org_id, name="Acme", slug="acme", owner_id=owner_id, description=None, logo_url=None, is_active=True, is_verified=False, settings={}, created_at=organization_service.utc_now_naive(), updated_at=organization_service.utc_now_naive())
        updated = SimpleNamespace(**{**created.__dict__, "name": "Acme 2"})

        with patch("swx_core.services.organization_service.organization_repository") as mock_repo:
            mock_repo.get_organization_by_slug = AsyncMock(side_effect=[None, None])
            mock_repo.create_organization = AsyncMock(return_value=created)
            mock_repo.add_member = AsyncMock()
            mock_repo.get_member = AsyncMock(return_value=SimpleNamespace(role=OrganizationRole.OWNER.value, is_active=True))
            mock_repo.update_organization = AsyncMock(return_value=updated)
            mock_repo.get_organization_by_id = AsyncMock(return_value=created)
            mock_repo.delete_organization = AsyncMock(return_value=True)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                created_public = await organization_service.create_organization(session, OrganizationCreate(name="Acme", slug="acme"), owner_id)
                updated_public = await organization_service.update_organization(session, org_id, OrganizationUpdate(name="Acme 2"), owner_id)
                deleted = await organization_service.delete_organization(session, org_id, owner_id)

        assert created_public.slug == "acme"
        assert updated_public.name == "Acme 2"
        assert deleted is True
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["organization.created", "organization.updated", "organization.deleted"]

    async def test_member_joined_emits_event(self):
        from swx_core.services import organization_service

        session = AsyncMock()
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        inviter_id = uuid.uuid4()
        invitation = SimpleNamespace(id=uuid.uuid4(), organization_id=org_id, inviter_id=inviter_id, role=OrganizationRole.MEMBER.value, status="PENDING", expires_at=organization_service.utc_now_naive() + timedelta(days=1))
        member = SimpleNamespace(id=uuid.uuid4(), organization_id=org_id, user_id=user_id, role=OrganizationRole.MEMBER.value, is_active=True, invited_by=inviter_id, joined_at=organization_service.utc_now_naive(), created_at=organization_service.utc_now_naive(), updated_at=organization_service.utc_now_naive())

        with patch("swx_core.services.organization_service.organization_repository") as mock_repo:
            mock_repo.get_invitation_by_token = AsyncMock(return_value=invitation)
            mock_repo.get_member = AsyncMock(return_value=None)
            mock_repo.add_member = AsyncMock(return_value=member)
            mock_repo.update_invitation_status = AsyncMock()
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await organization_service.accept_invitation(session, "token", user_id)

        assert result.user_id == user_id
        assert mock_dispatch.call_args.args[0] == "organization.member_joined"
        assert mock_dispatch.call_args.kwargs["payload"]["role"] == OrganizationRole.MEMBER.value

    async def test_member_removed_and_role_changed_emit_events(self):
        from swx_core.services import organization_service

        session = AsyncMock()
        org_id = uuid.uuid4()
        member_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        member_user_id = uuid.uuid4()
        member = SimpleNamespace(id=member_id, organization_id=org_id, user_id=member_user_id, role=OrganizationRole.ADMIN.value, is_active=True, invited_by=requester_id, joined_at=organization_service.utc_now_naive(), created_at=organization_service.utc_now_naive(), updated_at=organization_service.utc_now_naive())

        with patch("swx_core.services.organization_service.organization_repository") as mock_repo:
            mock_repo.get_member = AsyncMock(return_value=SimpleNamespace(role=OrganizationRole.OWNER.value, is_active=True))
            mock_repo.update_member_role = AsyncMock(return_value=member)
            mock_repo.get_organization_members = AsyncMock(return_value=[member])
            mock_repo.remove_member = AsyncMock(return_value=True)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                updated = await organization_service.update_member_role(session, org_id, member_id, OrganizationRole.VIEWER.value, requester_id)
                removed = await organization_service.remove_member(session, org_id, member_id, requester_id)

        assert updated.user_id == member_user_id
        assert removed is True
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["organization.member_role_changed", "organization.member_removed"]
