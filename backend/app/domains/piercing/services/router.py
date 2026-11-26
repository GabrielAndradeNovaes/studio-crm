from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import StudioRole
from app.core.module_guard import require_module
from app.core.rbac import TenantContext, require_roles
from app.domains.piercing.services.schemas import (
    PiercingServiceCreateRequest,
    PiercingServiceResponse,
    PiercingServiceUpdateRequest,
)
from app.domains.piercing.services.service import (
    create_piercing_service,
    get_piercing_service,
    list_piercing_services,
    soft_delete_piercing_service,
    update_piercing_service,
)

router = APIRouter(
    prefix="/services",
    tags=["Module Piercing - Services"],
    dependencies=[Depends(require_module("piercing"))],
)


@router.get("", response_model=list[PiercingServiceResponse])
async def list_services_endpoint(
    q: str | None = Query(default=None, max_length=120),
    anatomical_site: str | None = Query(default=None, max_length=80),
    active_only: bool = Query(default=False),
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> list[PiercingServiceResponse]:
    rows = await list_piercing_services(
        db, tenant, q=q, anatomical_site=anatomical_site, active_only=active_only
    )
    return [PiercingServiceResponse.model_validate(r) for r in rows]


@router.get("/{service_id}", response_model=PiercingServiceResponse)
async def get_service_endpoint(
    service_id: uuid.UUID,
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> PiercingServiceResponse:
    service = await get_piercing_service(db, tenant, service_id)
    return PiercingServiceResponse.model_validate(service)


@router.post(
    "",
    response_model=PiercingServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_endpoint(
    payload: PiercingServiceCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> PiercingServiceResponse:
    service = await create_piercing_service(db, tenant, payload, request=request)
    return PiercingServiceResponse.model_validate(service)


@router.patch("/{service_id}", response_model=PiercingServiceResponse)
async def update_service_endpoint(
    service_id: uuid.UUID,
    payload: PiercingServiceUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> PiercingServiceResponse:
    service = await update_piercing_service(
        db, tenant, service_id, payload, request=request
    )
    return PiercingServiceResponse.model_validate(service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_endpoint(
    service_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await soft_delete_piercing_service(db, tenant, service_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
