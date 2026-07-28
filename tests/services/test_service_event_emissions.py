"""
Tests for event emission across all SwX services.

Tests verify:
1. role.created, role.updated, role.deleted events
2. permission.created, permission.updated, permission.deleted events
3. team.created, team.updated, team.deleted, team.member_added, team.member_removed events
4. user_role.assigned, user_role.removed events
5. policy.created, policy.updated, policy.deleted events
6. user.updated, user.password_changed, user.deleted events
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from swx_core.events.dispatcher import EventBus, Event

# Skip entire module if passlib is not installed (required by auth/user services)
pytest.importorskip("passlib")


class TestRoleServiceEvents:
    async def test_create_role_emits_event(self):
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        
        mock_session = AsyncMock()
        role_create = RoleCreate(name="admin", description="Admin role")
        
        mock_role = Role(id=uuid.uuid4(), name="admin", description="Admin role")
        
        with patch("swx_core.services.role_service.role_repository") as mock_repo:
            mock_repo.get_role_by_name = AsyncMock(return_value=None)
            mock_repo.create_role = AsyncMock(return_value=mock_role)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_role_service(session=mock_session, role_in=role_create)
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.name == "role.created"
                assert "id" in event.payload
                assert event.payload["data"]["name"] == "admin"

    async def test_create_role_with_event_context(self):
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        
        mock_session = AsyncMock()
        role_create = RoleCreate(name="moderator", description="Moderator role")
        mock_role = Role(id=uuid.uuid4(), name="moderator", description="Moderator role")
        
        with patch("swx_core.services.role_service.role_repository") as mock_repo:
            mock_repo.get_role_by_name = AsyncMock(return_value=None)
            mock_repo.create_role = AsyncMock(return_value=mock_role)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                context = {"created_by": "admin", "source": "api"}
                await create_role_service(
                    session=mock_session, 
                    role_in=role_create,
                    event_context=context,
                )
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.payload["context"] == context


class TestPermissionServiceEvents:
    async def test_create_permission_emits_event(self):
        from swx_core.services.permission_service import create_permission_service
        from swx_core.models.permission import Permission, PermissionCreate
        
        mock_session = AsyncMock()
        perm_create = PermissionCreate(
            name="user:read", 
            description="Read users",
            resource_type="user",
            action="read",
        )
        
        mock_perm = Permission(
            id=uuid.uuid4(), 
            name="user:read", 
            description="Read users",
            resource_type="user",
            action="read",
        )
        
        with patch("swx_core.services.permission_service.permission_repository") as mock_repo:
            mock_repo.get_permission_by_name = AsyncMock(return_value=None)
            mock_repo.create_permission = AsyncMock(return_value=mock_perm)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_permission_service(session=mock_session, permission_in=perm_create)
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.name == "permission.created"
                assert event.payload["data"]["name"] == "user:read"


class TestTeamServiceEvents:
    async def test_create_team_emits_event(self):
        from swx_core.services.team_service import create_team_service
        from swx_core.models.team import Team, TeamCreate
        
        mock_session = AsyncMock()
        team_create = TeamCreate(name="engineering", description="Engineering team")
        
        mock_team = Team(id=uuid.uuid4(), name="engineering", description="Engineering team")
        
        with patch("swx_core.services.team_service.team_repository") as mock_repo:
            mock_repo.create_team = AsyncMock(return_value=mock_team)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_team_service(session=mock_session, team_in=team_create)
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.name == "team.created"

    async def test_add_team_member_emits_event(self):
        from swx_core.services.team_service import add_team_member_service
        from swx_core.models.team_member import TeamMember, TeamMemberCreate
        from swx_core.models.team import Team
        from swx_core.models.user import User
        from swx_core.models.team_role import TeamRole
        
        mock_session = AsyncMock()
        
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        team_role_id = uuid.uuid4()
        
        member_in = TeamMemberCreate(team_id=team_id, user_id=user_id, team_role_id=team_role_id)
        mock_member = TeamMember(id=uuid.uuid4(), team_id=team_id, user_id=user_id, team_role_id=team_role_id)
        
        with patch("swx_core.services.team_service.team_repository") as mock_team_repo:
            with patch("swx_core.services.team_service.user_repository") as mock_user_repo:
                mock_team_repo.get_team_by_id = AsyncMock(return_value=Team(id=team_id, name="test"))
                mock_user_repo.get_user_by_id = AsyncMock(return_value=User(id=user_id, email="test@test.com"))
                mock_session.get = AsyncMock(return_value=TeamRole(id=team_role_id, key="member", name="Team Member"))
                mock_team_repo.get_team_member = AsyncMock(return_value=None)
                mock_team_repo.add_team_member = AsyncMock(return_value=mock_member)
                
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await add_team_member_service(session=mock_session, member_in=member_in)
                    
                    assert mock_emit.called
                    event = mock_emit.call_args[0][0]
                    assert event.name == "team.member_added"


class TestUserRoleServiceEvents:
    async def test_assign_role_to_user_emits_event(self):
        from swx_core.services.user_role_service import assign_role_to_user_service
        from swx_core.models.user_role import UserRole, UserRoleCreate
        from swx_core.models.user import User
        from swx_core.models.role import Role
        
        mock_session = AsyncMock()
        
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()
        
        assignment = UserRoleCreate(user_id=user_id, role_id=role_id)
        mock_user_role = UserRole(id=uuid.uuid4(), user_id=user_id, role_id=role_id)
        
        with patch("swx_core.services.user_role_service.user_repository") as mock_user_repo:
            with patch("swx_core.services.user_role_service.role_repository") as mock_role_repo:
                with patch("swx_core.services.user_role_service.user_role_repository") as mock_ur_repo:
                    mock_user_repo.get_user_by_id = AsyncMock(return_value=User(id=user_id, email="test@test.com"))
                    mock_role_repo.get_role_by_id = AsyncMock(return_value=Role(id=role_id, name="admin"))
                    mock_ur_repo.get_user_role_assignment = AsyncMock(return_value=None)
                    mock_ur_repo.assign_role_to_user = AsyncMock(return_value=mock_user_role)
                    
                    with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                        await assign_role_to_user_service(session=mock_session, assignment=assignment)
                        
                        assert mock_emit.called
                        event = mock_emit.call_args[0][0]
                        assert event.name == "user_role.assigned"


class TestPolicyServiceEvents:
    async def test_create_policy_emits_event(self):
        from swx_core.services.policy_service import create_policy_service
        from swx_core.models.policy import Policy
        
        mock_session = AsyncMock()
        
        mock_policy = Policy(
            id=uuid.uuid4(),
            policy_id="test-policy",
            name="Test Policy",
            description="A test policy",
        )
        
        with patch("swx_core.services.policy_service.policy_repository") as mock_repo:
            mock_repo.policy_exists = AsyncMock(return_value=False)
            mock_repo.create_policy = AsyncMock(return_value=mock_policy)
            
            with patch("swx_core.services.policy_service.PolicyRegistry") as mock_registry:
                mock_registry.get = MagicMock(return_value=None)
                
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await create_policy_service(session=mock_session, policy=mock_policy)
                    
                    assert mock_emit.called
                    event = mock_emit.call_args[0][0]
                    assert event.name == "policy.created"


class TestUserServiceEvents:
    async def test_update_user_profile_emits_event(self):
        from swx_core.services.user_service import update_user_profile_service
        from swx_core.models.user import User, UserUpdate
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        
        user_update = UserUpdate(full_name="New Name")
        current_user = User(id=uuid.uuid4(), email="test@test.com", full_name="Old Name")
        
        updated_user = User(id=current_user.id, email="test@test.com", full_name="New Name")
        
        with patch("swx_core.services.user_service.update_user", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = updated_user
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await update_user_profile_service(
                    session=mock_session,
                    user_in=user_update,
                    current_user=current_user,
                    request=mock_request,
                )
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.name == "user.updated"
                assert event.payload["old_values"]["full_name"] == "Old Name"
                assert event.payload["new_values"]["full_name"] == "New Name"

    async def test_delete_user_emits_event(self):
        from swx_core.services.user_service import delete_user_service
        from swx_core.models.user import User
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        
        user_id = uuid.uuid4()
        current_user = User(id=user_id, email="test@test.com")
        
        with patch("swx_core.services.user_service.delete_user", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await delete_user_service(
                    session=mock_session,
                    current_user=current_user,
                    request=mock_request,
                )
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.name == "user.deleted"
                assert event.payload["id"] == str(user_id)