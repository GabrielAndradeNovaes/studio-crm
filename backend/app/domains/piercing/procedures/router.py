from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.module_guard import require_module
from app.core.rbac import TenantContext
from app.domains.piercing.procedures.schemas import (
    CompleteDownsizeRequest,
    DownsizeWindowFilter,
    PiercingProcedureCreateRequest,
    PiercingProcedureResponse,
    PiercingProcedureUpdateRequest,
)
from app.domains.piercing.procedures.service import (
    complete_downsize_return,
    create_piercing_procedure,
    list_downsize_reminders,
    list_piercing_procedures,
    update_piercing_procedure,
)

router = APIRouter(
    prefix="/procedures",
    tags=["Module Piercing - Technical Procedures & Downsize"],
    dependencies=[Depends(require_module("piercing"))],
)


@router.get("", response_model=list[PiercingProcedureResponse])
async def list_procedures_endpoint(
    client_id: uuid.UUID | None = Query(default=None),
    professional_id: uuid.UUID | None = Query(default=None),
    appointment_id: uuid.UUID | None = Query(default=None),
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> list[PiercingProcedureResponse]:
    return await list_piercing_procedures(
        db,
        tenant,
        client_id=client_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
    )


@router.get("/downsize-reminders", response_model=list[PiercingProcedureResponse])
async def list_downsize_reminders_endpoint(
    window: DownsizeWindowFilter = Query(default="all_pending"),
    professional_id: uuid.UUID | None = Query(default=None),
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> list[PiercingProcedureResponse]:
    return await list_downsize_reminders(
        db, tenant, window=window, professional_id=professional_id
    )


@router.post(
    "",
    response_model=PiercingProcedureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_procedure_endpoint(
    payload: PiercingProcedureCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> PiercingProcedureResponse:
    return await create_piercing_procedure(db, tenant, payload, request=request)


@router.patch("/{procedure_id}", response_model=PiercingProcedureResponse)
async def update_procedure_endpoint(
    procedure_id: uuid.UUID,
    payload: PiercingProcedureUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> PiercingProcedureResponse:
    return await update_piercing_procedure(
        db, tenant, procedure_id, payload, request=request
    )


@router.post(
    "/{procedure_id}/complete-downsize",
    response_model=PiercingProcedureResponse,
)
async def complete_downsize_endpoint(
    procedure_id: uuid.UUID,
    payload: CompleteDownsizeRequest,
    request: Request,
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> PiercingProcedureResponse:
    return await complete_downsize_return(
        db, tenant, procedure_id, payload, request=request
    )
