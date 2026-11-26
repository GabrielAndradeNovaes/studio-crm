from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import StudioRole
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.users.schemas import (
    TeamMemberCreateRequest,
    TeamMemberDirectoryResponse,
    TeamMemberOwnerResponse,
    TeamMemberUpdateRequest,
)
from app.domains.core.users.service import (
    add_team_member,
    deactivate_team_member,
    get_my_membership_profile,
    list_team_directory,
    list_team_for_owner,
    update_team_member,
)

router = APIRouter(prefix="/team", tags=["Team & RBAC"])


@router.get("/me", response_model=TeamMemberOwnerResponse)
async def read_my_team_profile(
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberOwnerResponse:
    return await get_my_membership_profile(db, tenant)


@router.get("/directory", response_model=list[TeamMemberDirectoryResponse])
async def read_team_directory(
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMemberDirectoryResponse]:
    return await list_team_directory(db, tenant)


@router.get("", response_model=list[TeamMemberOwnerResponse])
async def read_full_team_for_owner(
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMemberOwnerResponse]:
    return await list_team_for_owner(db, tenant)


@router.post(
    "",
    response_model=TeamMemberOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team_member_endpoint(
    payload: TeamMemberCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberOwnerResponse:
    return await add_team_member(db, tenant, payload, request=request)


@router.patch("/{membership_id}", response_model=TeamMemberOwnerResponse)
async def patch_team_member_endpoint(
    membership_id: uuid.UUID,
    payload: TeamMemberUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberOwnerResponse:
    return await update_team_member(db, tenant, membership_id, payload, request=request)


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_member_endpoint(
    membership_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await deactivate_team_member(db, tenant, membership_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
