from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, select
from swx_core.models.billing import BillingAccount, BillingAccountType, Subscription, UsageRecord
from swx_core.models.team import Team, TeamCreate, TeamUpdate
from swx_core.models.team_member import TeamMember, TeamMemberCreate
from swx_core.models.team_role import TeamRole
from swx_core.repositories import team_repository, user_repository
from swx_core.events.dispatcher import event_bus, Event
from swx_core.services.billing.subscription_service import SubscriptionService


async def list_teams_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Team]:
    return await team_repository.get_all_teams(session, skip, limit)


async def list_user_teams_service(
    session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
) -> List[Team]:
    """List teams where user is a member."""
    stmt = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)  # pyright: ignore[reportArgumentType]
        .where(TeamMember.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_team_service(session: AsyncSession, team_id: UUID, user_id: UUID) -> Team:
    """Get team if user is a member."""
    team = await team_repository.get_team_by_id(session, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    member_result = await session.execute(
        select(TeamMember).where(
            and_(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this team")
    
    return team


async def create_team_service(
    session: AsyncSession, 
    team_in: TeamCreate,
    event_context: Dict[str, Any] | None = None,
) -> Team:
    team = await team_repository.create_team(session, team_in)
    subscription_service = SubscriptionService(session)
    await subscription_service.get_or_create_account(
        owner_id=team.id,
        account_type=BillingAccountType.TEAM,
    )
    
    await event_bus.emit(Event(
        name="team.created",
        payload={
            "id": str(team.id),
            "data": {"name": team.name, "description": team.description},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return team


async def get_team_service(session: AsyncSession, team_id: UUID) -> Team:
    team = await team_repository.get_team_by_id(session, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def update_team_service(
    session: AsyncSession, 
    team_id: UUID, 
    team_in: TeamUpdate,
    event_context: Dict[str, Any] | None = None,
) -> Team:
    team = await get_team_service(session, team_id)
    old_values = {"name": team.name, "description": team.description}
    team = await team_repository.update_team(session, team, team_in)
    new_values = {"name": team.name, "description": team.description}
    
    await event_bus.emit(Event(
        name="team.updated",
        payload={
            "id": str(team.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return team


async def delete_team_service(
    session: AsyncSession, 
    team_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    team = await get_team_service(session, team_id)
    
    members = await team_repository.list_team_members(session, team_id)
    if members:
        raise HTTPException(status_code=400, detail="Cannot delete team with members")

    billing_accounts_stmt = select(BillingAccount.id).where(
        and_(
            BillingAccount.owner_id == team_id,
            BillingAccount.account_type == BillingAccountType.TEAM,
        )
    )
    billing_accounts_result = await session.execute(billing_accounts_stmt)
    billing_account_ids = list(billing_accounts_result.scalars().all())

    if billing_account_ids:
        # Bulk delete usage records for all subscriptions in the team's billing accounts
        from sqlalchemy import delete as sql_delete

        subscription_ids_stmt = select(Subscription.id).where(
            Subscription.account_id.in_(billing_account_ids)  # pyright: ignore[reportAttributeAccessIssue]
        )
        subscription_ids_result = await session.execute(subscription_ids_stmt)
        subscription_ids = list(subscription_ids_result.scalars().all())

        if subscription_ids:
            await session.execute(
                sql_delete(UsageRecord).where(
                    UsageRecord.subscription_id.in_(subscription_ids)  # pyright: ignore[reportAttributeAccessIssue]
                )
            )
            await session.execute(
                sql_delete(Subscription).where(
                    Subscription.account_id.in_(billing_account_ids)  # pyright: ignore[reportAttributeAccessIssue]
                )
            )

        await session.execute(
            sql_delete(BillingAccount).where(
                BillingAccount.id.in_(billing_account_ids)  # pyright: ignore[reportAttributeAccessIssue]
            )
        )
         
    await team_repository.delete_team(session, team)
    
    await event_bus.emit(Event(
        name="team.deleted",
        payload={
            "id": str(team_id),
            "data": {"name": team.name},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


async def add_team_member_service(
    session: AsyncSession, 
    member_in: TeamMemberCreate,
    event_context: Dict[str, Any] | None = None,
) -> TeamMember:
    await get_team_service(session, member_in.team_id)
    
    user = await user_repository.get_user_by_id(session, member_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    team_role = await session.get(TeamRole, member_in.team_role_id)
    if not team_role:
        raise HTTPException(status_code=404, detail="Team role not found")
        
    existing = await team_repository.get_team_member(session, member_in.team_id, member_in.user_id)
    if existing:
        existing.team_role_id = member_in.team_role_id
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing
        
    member = await team_repository.add_team_member(session, member_in)
    
    await event_bus.emit(Event(
        name="team.member_added",
        payload={
            "id": str(member.id),
            "data": {"team_id": str(member_in.team_id), "user_id": str(member_in.user_id), "team_role_id": str(member_in.team_role_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return member


async def remove_team_member_service(
    session: AsyncSession, 
    member_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    member = await team_repository.get_team_member_by_id(session, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    await team_repository.remove_team_member(session, member)
    
    await event_bus.emit(Event(
        name="team.member_removed",
        payload={
            "id": str(member_id),
            "data": {"team_id": str(member.team_id), "user_id": str(member.user_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


async def list_team_members_service(session: AsyncSession, team_id: UUID) -> List[TeamMember]:
    await get_team_service(session, team_id)
    return await team_repository.list_team_members(session, team_id)
