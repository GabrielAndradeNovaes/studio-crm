from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import AppointmentStatus, StudioRole
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.appointments.schemas import (
    AppointmentCreateRequest,
    AppointmentDepositRefundRequest,
    AppointmentDepositRequest,
    AppointmentResponse,
    AppointmentUpdateRequest,
)
from app.domains.core.appointments.service import (
    create_appointment,
    get_appointment_detail,
    list_appointments,
    refund_appointment_deposit,
    register_appointment_deposit,
    soft_delete_appointment,
    update_appointment,
)

router = APIRouter(prefix="/appointments", tags=["Schedule & Appointments"])


@router.get("", response_model=list[AppointmentResponse])
async def list_appointments_endpoint(
    professional_id: uuid.UUID | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentResponse]:
    return await list_appointments(
        db,
        tenant,
        professional_id=professional_id,
        client_id=client_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment_endpoint(
    appointment_id: uuid.UUID,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    return await get_appointment_detail(db, tenant, appointment_id)


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_endpoint(
    payload: AppointmentCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    return await create_appointment(db, tenant, payload, request=request)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment_endpoint(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    return await update_appointment(
        db, tenant, appointment_id, payload, request=request
    )


@router.post(
    "/{appointment_id}/deposit",
    response_model=AppointmentResponse,
)
async def register_deposit_endpoint(
    appointment_id: uuid.UUID,
    payload: AppointmentDepositRequest,
    request: Request,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    return await register_appointment_deposit(
        db, tenant, appointment_id, payload, request=request
    )


@router.post(
    "/{appointment_id}/deposit/refund",
    response_model=AppointmentResponse,
)
async def refund_deposit_endpoint(
    appointment_id: uuid.UUID,
    payload: AppointmentDepositRefundRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    return await refund_appointment_deposit(
        db, tenant, appointment_id, payload, request=request
    )


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment_endpoint(
    appointment_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await soft_delete_appointment(db, tenant, appointment_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
