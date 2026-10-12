# Organizations
**Version:** 1.0.0  
**Last Updated:** 2026-07-28
---
## Table of Contents
1. [Overview](#overview)
2. [Organization vs Team](#organization-vs-team)
3. [Database Models](#database-models)
4. [Organization Roles](#organization-roles)
5. [Invitation Lifecycle](#invitation-lifecycle)
6. [Configuration](#configuration)
7. [API Endpoints](#api-endpoints)
8. [Usage Examples](#usage-examples)
9. [Events](#events)
10. [Best Practices](#best-practices)
---
## Overview
Organizations add a business level grouping to SwX-Core. Teams are built for day to day collaboration and scoped work, while organizations represent the wider business entity that owns members, identity, and organization level settings.
- **Organization roles** are stored per member with `owner`, `admin`, `member`, `viewer`, and `api_only`
- **Invitation based membership** uses email invites, tokens, expiration windows, and tracked acceptance or rejection states
- **JSONB settings** live on `Organization.settings`, which allows per organization configuration without schema changes
- **Events** are dispatched for organization creation, invitation sending, and member joins
- **Admin and user APIs** are separated into `/admin/organizations` and `/user/organizations`
---
## Organization vs Team
Organizations and teams are related but they solve different problems.
| Concept | Best for | Typical scope | Membership model | Example use |
|---|---|---|---|---|
| Organization | Business identity and ownership | Company or business account | Direct organization members with organization roles | A company account that owns settings and invites business users |
| Team | Collaboration and operational work | Department, project, or working group | Team members with team specific roles | A support team, engineering squad, or project workspace |
Use an **organization** when you need a business container with a stable slug, shared settings, and organization wide membership. Use a **team** when you need operational grouping, collaboration boundaries, or tenant scoped application data.
---
## Database Models
The organization feature uses three tables.
### `swx_organization`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | string | Indexed organization name, max length 255 |
| `slug` | string | Unique indexed slug, max length 100 |
| `description` | string, nullable | Optional description, max length 500 |
| `logo_url` | string, nullable | Optional logo URL, max length 500 |
| `owner_id` | UUID, nullable | References `swx_users.id`, `SET NULL` on delete |
| `is_active` | bool | Activation flag |
| `is_verified` | bool | Verification flag |
| `settings` | JSONB | Arbitrary organization settings, defaults to `{}` |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
### `swx_organization_member`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `organization_id` | UUID | References `swx_organization.id`, cascade delete |
| `user_id` | UUID | References `swx_users.id`, cascade delete |
| `role` | string | Role string, defaults to `member` |
| `is_active` | bool | Active membership flag |
| `invited_by` | UUID, nullable | User who invited the member |
| `joined_at` | datetime | When the member joined |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
Constraint:
- `uq_org_member_user_org` enforces one membership row per `organization_id` and `user_id`
### `swx_organization_invitation`
| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `organization_id` | UUID | References `swx_organization.id`, cascade delete |
| `inviter_id` | UUID | References `swx_users.id`, cascade delete |
| `invitee_email` | string | Indexed recipient email, max length 255 |
| `role` | string | Role to assign on acceptance |
| `message` | string, nullable | Optional invite message, max length 500 |
| `expires_at` | datetime | Expiration timestamp |
| `status` | string | Invitation state, defaults to `PENDING` |
| `token` | string | Unique indexed token, max length 64 |
| `accepted_at` | datetime, nullable | When the invitation was accepted |
| `rejected_at` | datetime, nullable | When the invitation was rejected |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
---
## Organization Roles
Roles are defined in `OrganizationRole` in `swx_core/models/organization.py`.
| Role | Description | Permissions in service layer |
|---|---|---|
| `owner` | Primary business owner of the organization | Can delete the organization, can act as admin member |
| `admin` | Administrative organization member | Can invite members and update member roles through service functions |
| `member` | Standard active member | Can view organization details, list members, list pending invitations, update organization through current service checks |
| `viewer` | Read focused member | Stored role for restricted access patterns |
| `api_only` | Non interactive or integration focused member | Stored role for automation or API based access patterns |
Current service enforcement treats `owner` and `admin` as administrative roles through `_require_admin_member()`. Deletion is stricter and only allows the `owner_id` stored on the organization record.
---
## Invitation Lifecycle
Organization invitations reuse `InvitationStatus` values from `swx_core/models/team_invitation.py`.
```text
PENDING -> ACCEPTED
PENDING -> REJECTED
PENDING -> EXPIRED
```
- **`PENDING`**: New invitation state created by `invite_member()`
- **`ACCEPTED`**: Set by `accept_invitation()`, which also creates or reuses an organization member row
- **`REJECTED`**: Set by `reject_invitation()`
- **`EXPIRED`**: Applied by `accept_invitation()` when `expires_at <= now`
Accepted invitations emit `organization.member_joined`. Sent invitations emit `organization.invitation_sent`.
---
## Configuration
Organization behavior is controlled in `swx_core/config/settings.py`.
```python
ORGANIZATION_ENABLED: bool = Field(
    default=True, description="Enable organization management framework"
)
ORGANIZATION_MAX_MEMBERS: int = Field(
    default=0, description="Maximum members allowed per organization (0 = unlimited)"
)
ORGANIZATION_INVITATION_EXPIRY_DAYS: int = Field(
    default=7, description="Days before organization invitations expire"
)
```
- **`ORGANIZATION_ENABLED`**: Global feature switch for the framework.
- **`ORGANIZATION_MAX_MEMBERS`**: Member cap checked in `invite_member()`. `0` means unlimited.
- **`ORGANIZATION_INVITATION_EXPIRY_DAYS`**: Number of days added to `expires_at` when an invitation is created.
---
## API Endpoints
### Admin Endpoints
All admin organization routes require `get_current_admin_user`.
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/organizations/` | List organizations with `skip` and `limit` |
| `GET` | `/admin/organizations/{org_id}` | Get one organization by ID |
| `POST` | `/admin/organizations/` | Create an organization. `owner_id` is required in the request body |
| `PUT` | `/admin/organizations/{org_id}` | Update an organization using the stored owner as acting user |
| `DELETE` | `/admin/organizations/{org_id}` | Delete an organization. Only the owner can delete |
| `GET` | `/admin/organizations/{org_id}/members` | List organization members |
| `POST` | `/admin/organizations/{org_id}/invitations` | Send an organization invitation |
| `GET` | `/admin/organizations/{org_id}/invitations` | List pending invitations |
### User Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/user/organizations/` | List the current user's organization membership rows |
| `POST` | `/user/organizations/accept-invitation` | Accept an invitation using a token payload |
| `POST` | `/user/organizations/reject-invitation` | Reject an invitation using a token payload |
| `DELETE` | `/user/organizations/{org_id}/leave` | Leave an organization |
---
## Usage Examples
The service layer lives in `swx_core/services/organization_service.py` and exposes the main workflows directly.
### Creating an Organization
```python
from uuid import UUID

from swx_core.models.organization import OrganizationCreate
from swx_core.services import organization_service

owner_id = UUID("11111111-1111-1111-1111-111111111111")

organization = await organization_service.create_organization(
    session=session,
    data=OrganizationCreate(
        name="Acme Holdings",
        slug="acme-holdings",
        description="Parent business account for Acme products.",
        logo_url="https://cdn.example.com/acme/logo.png",
        settings={"billing_email": "ops@acme.example"},
    ),
    owner_id=owner_id,
)
```
`create_organization()` also adds the owner to `swx_organization_member` with the `owner` role.
### Inviting Members
```python
from uuid import UUID

from swx_core.models.organization_invitation import OrganizationInvitationCreate
from swx_core.services import organization_service

org_id = UUID("22222222-2222-2222-2222-222222222222")
inviter_id = UUID("11111111-1111-1111-1111-111111111111")

invitation = await organization_service.invite_member(
    session=session,
    org_id=org_id,
    data=OrganizationInvitationCreate(
        organization_id=org_id,
        invitee_email="new.user@example.com",
        role="admin",
        message="Join the organization as an admin.",
    ),
    inviter_id=inviter_id,
)
```
`invite_member()` checks `_require_admin_member()`, enforces `ORGANIZATION_MAX_MEMBERS`, generates a token, and sets `expires_at` from `ORGANIZATION_INVITATION_EXPIRY_DAYS`.
### Accepting Invitations
```python
from uuid import UUID

from swx_core.services import organization_service

user_id = UUID("33333333-3333-3333-3333-333333333333")

member = await organization_service.accept_invitation(
    session=session,
    token="secure-invitation-token",
    user_id=user_id,
)
```
If the user is not already a member, `accept_invitation()` creates the membership with the invited role and marks the invitation as `ACCEPTED`.
### Managing Members
```python
from uuid import UUID

from swx_core.models.organization import OrganizationRole
from swx_core.services import organization_service

org_id = UUID("22222222-2222-2222-2222-222222222222")
member_id = UUID("44444444-4444-4444-4444-444444444444")
requester_id = UUID("11111111-1111-1111-1111-111111111111")

updated_member = await organization_service.update_member_role(
    session=session,
    org_id=org_id,
    member_id=member_id,
    role=OrganizationRole.VIEWER.value,
    requester_id=requester_id,
)

removed = await organization_service.remove_member(
    session=session,
    org_id=org_id,
    member_id=member_id,
    requester_id=requester_id,
)
```
These service functions exist even though there are no dedicated member role or member removal routes in the current organization route files.
---
## Events
The organization service dispatches events through `swx_core.events.event_bus`.
| Event name | Payload | When emitted |
|---|---|---|
| `organization.created` | `{"organization_id": str(organization.id), "owner_id": str(owner_id), "slug": organization.slug}` | After `create_organization()` creates the organization and owner membership |
| `organization.invitation_sent` | `{"organization_id": str(org_id), "invitation_id": str(invitation.id), "invitee_email": invitation.invitee_email}` | After `invite_member()` creates an invitation |
| `organization.member_joined` | `{"organization_id": str(invitation.organization_id), "user_id": str(user_id), "role": public_member.role}` | After `accept_invitation()` marks the invitation accepted |
---
## Best Practices
- Keep organization `slug` values stable because `create_organization()` and `update_organization()` enforce uniqueness.
- Use `settings` for business metadata that changes per organization but does not justify a schema migration.
- Reserve `owner` and `admin` for users who should manage invitations and member level changes.
- Set `ORGANIZATION_MAX_MEMBERS` in production if your plan model or business rules require hard limits.
- Process invitation acceptance quickly or surface expiration dates clearly to users, since expired invitations are rejected during acceptance.
- Use teams for working groups and tenant scoped workflows, and use organizations for business identity and top level ownership.
---
**Status:** Organization model documented, ready for use.
