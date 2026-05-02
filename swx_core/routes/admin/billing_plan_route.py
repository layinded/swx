"""
Plan Management Routes
----------------------
Admin-only APIs for managing plans and entitlements.
"""

from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.database.db import SessionDep
from swx_core.models.billing import Plan, PlanEntitlement, Feature
from swx_core.auth.admin.dependencies import AdminUserDep, get_current_admin_user

router = APIRouter(
    prefix="/admin/billing/plan",
    tags=["admin-billing"],
    dependencies=[Depends(get_current_admin_user)]
)

@router.get("/", response_model=List[Plan])
async def list_plans(session: SessionDep):
    """List all billing plans."""
    stmt = select(Plan)
    result = await session.execute(stmt)
    return list(result.scalars().all())

@router.post("/", response_model=Plan, status_code=status.HTTP_201_CREATED)
async def create_plan(plan: Plan, session: SessionDep):
    """Create a new billing plan."""
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan

@router.post("/{plan_id}/entitlement/{feature_id}")
async def assign_entitlement(
    plan_id: UUID, 
    feature_id: UUID, 
    value: str, 
    session: SessionDep
):
    """Assign an entitlement to a plan."""
    entitlement = PlanEntitlement(
        plan_id=plan_id,
        feature_id=feature_id,
        value=value
    )
    session.add(entitlement)
    await session.commit()
    return {"message": "Entitlement assigned"}
