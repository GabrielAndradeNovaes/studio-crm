from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac import AuthenticatedPrincipal, require_superadmin
from app.domains.core.studios.schemas import (
    StudioResponse,
    SuperadminCreateStudioRequest,
    SuperadminUpdateStudioGovernanceRequest,
)
from app.domains.core.studios.service import (
    create_studio_by_superadmin,
    list_studios_superadmin,
    update_studio_governance_by_superadmin,
)

router = APIRouter(prefix="/admin/studios", tags=["SaaS SuperAdmin - Studios"])


@router.get("", response_model=list[StudioResponse])
async def list_studios_endpoint(
    _admin: AuthenticatedPrincipal = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> list[StudioResponse]:
    studios = await list_studios_superadmin(db)
    return [StudioResponse.model_validate(s) for s in studios]


@router.post("", response_model=StudioResponse, status_code=status.HTTP_201_CREATED)
async def create_studio_endpoint(
    payload: SuperadminCreateStudioRequest,
    request: Request,
    admin: AuthenticatedPrincipal = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> StudioResponse:
    studio = await create_studio_by_superadmin(db, payload, actor=admin, request=request)
    return StudioResponse.model_validate(studio)


@router.patch("/{studio_id}", response_model=StudioResponse)
async def update_studio_governance_endpoint(
    studio_id: uuid.UUID,
    payload: SuperadminUpdateStudioGovernanceRequest,
    request: Request,
    admin: AuthenticatedPrincipal = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> StudioResponse:
    studio = await update_studio_governance_by_superadmin(
        db, studio_id, payload, actor=admin, request=request
    )
    return StudioResponse.model_validate(studio)
