"""
Core Models
-----------
This module exports all core framework models.
"""

from swx_core.models.base import Base
from swx_core.models.common import Message
from swx_core.models.permission import (
    Permission,
    PermissionCreate,
    PermissionUpdate,
    PermissionPublic,
)
from swx_core.models.refresh_token import (
    RefreshToken,
    RefreshTokenCreate,
    RefreshTokenUpdate,
    RefreshTokenPublic,
)
from swx_core.models.role import (
    Role,
    RoleCreate,
    RoleUpdate,
    RolePublic,
)
from swx_core.models.role_permission import (
    RolePermission,
    RolePermissionCreate,
    RolePermissionPublic,
)
from swx_core.models.user_role import (
    UserRole,
    UserRoleCreate,
    UserRolePublic,
)
from swx_core.models.team import (
    Team,
    TeamCreate,
    TeamUpdate,
    TeamPublic,
)
from swx_core.models.team_member import (
    TeamMember,
    TeamMemberCreate,
    TeamMemberPublic,
)
from swx_core.models.token import (
    Token,
    TokenBase,
    TokenPayload,
    TokenRefreshRequest,
    NewPassword,
    RefreshTokenRequest,
    LogoutRequest,
)
from swx_core.models.admin_user import (
    AdminUser,
    AdminUserBase,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserPublic,
)
from swx_core.models.user import (
    User,
    UserBase,
    UserCreate,
    UserUpdate,
    UserPublic,
    UsersPublic,
    UserUpdatePassword,
    UserNewPassword,
)
from swx_core.models.policy import (
    Policy,
    PolicyEffect,
    ConditionOperator,
    Condition,
    PolicyDecision,
    PolicyEvaluation,
)
from swx_core.models.job import (
    Job,
    JobStatus,
    JobType,
    JobCreate,
    JobUpdate,
    JobPublic,
)
from swx_core.models.system_config import (
    SystemConfig,
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigPublic,
    SystemConfigHistory,
    SettingValueType,
    SettingCategory,
)

__all__ = [
    # Base
    "Base",
    "Message",
    # Permission
    "Permission",
    "PermissionCreate",
    "PermissionUpdate",
    "PermissionPublic",
    # Role
    "Role",
    "RoleCreate",
    "RoleUpdate",
    "RolePublic",
    # Role-Permission
    "RolePermission",
    "RolePermissionCreate",
    "RolePermissionPublic",
    # User-Role
    "UserRole",
    "UserRoleCreate",
    "UserRolePublic",
    # Team
    "Team",
    "TeamCreate",
    "TeamUpdate",
    "TeamPublic",
    # Team Member
    "TeamMember",
    "TeamMemberCreate",
    "TeamMemberPublic",
    # Token
    "Token",
    "TokenBase",
    "TokenPayload",
    "TokenRefreshRequest",
    "NewPassword",
    "RefreshTokenRequest",
    "LogoutRequest",
    # Refresh Token
    "RefreshToken",
    "RefreshTokenCreate",
    "RefreshTokenUpdate",
    "RefreshTokenPublic",
    # Admin User
    "AdminUser",
    "AdminUserBase",
    "AdminUserCreate",
    "AdminUserUpdate",
    "AdminUserPublic",
    # User
    "User",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserPublic",
    "UsersPublic",
    "UserUpdatePassword",
    "UserNewPassword",
    # Policy
    "Policy",
    "PolicyEffect",
    "ConditionOperator",
    "Condition",
    "PolicyDecision",
    "PolicyEvaluation",
    # Job
    "Job",
    "JobStatus",
    "JobType",
    "JobCreate",
    "JobUpdate",
    "JobPublic",
    # System Config
    "SystemConfig",
    "SystemConfigBase",
    "SystemConfigCreate",
    "SystemConfigUpdate",
    "SystemConfigPublic",
    "SystemConfigHistory",
    "SettingValueType",
    "SettingCategory",
]
