from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import LeadSource, StudioRole
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.clients.schemas import (
    ClientCreateRequest,
    ClientResponse,
    ClientUpdateRequest,
)
from app.domains.core.clients.service import (
    create_client,
    get_client_by_id,
    list_clients,
    soft_delete_client,
    update_client,
)

router = APIRouter(prefix="/clients", tags=["CRM - Clients"])


@router.get("", response_model=list[ClientResponse])
async def list_clients_endpoint(
    q: str | None = Query(default=None, max_length=120),
    lead_source: LeadSource | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=40),
    only_minors: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=300),
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[ClientResponse]:
    return await list_clients(
        db,
        tenant,
        q=q,
        lead_source=lead_source,
        tag=tag,
        only_minors=only_minors,
        offset=offset,
        limit=limit,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client_endpoint(
    client_id: uuid.UUID,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await get_client_by_id(db, tenant, client_id)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client_endpoint(
    payload: ClientCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await create_client(db, tenant, payload, request=request)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client_endpoint(
    client_id: uuid.UUID,
    payload: ClientUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await update_client(db, tenant, client_id, payload, request=request)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_endpoint(
    client_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await soft_delete_client(db, tenant, client_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
