"""
Feature Management Routes
-------------------------
Admin-only APIs for managing system features.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlmodel import select

from swx_core.database.db import SessionDep
from swx_core.models.billing import Feature
from swx_core.auth.admin.dependencies import get_current_admin_user

router = APIRouter(
    prefix="/admin/billing/feature",
    tags=["admin-billing"],
    dependencies=[Depends(get_current_admin_user)]
)

@router.get("/", response_model=List[Feature])
async def list_features(session: SessionDep):
    """List all billing features."""
    stmt = select(Feature)
    result = await session.execute(stmt)
    return list(result.scalars().all())

@router.post("/", response_model=Feature, status_code=status.HTTP_201_CREATED)
async def create_feature(feature: Feature, session: SessionDep):
    """Create a new billing feature."""
    session.add(feature)
    await session.commit()
    await session.refresh(feature)
    return feature
