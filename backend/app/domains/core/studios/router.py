from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import StudioRole
from app.core.rate_limit import rate_limit_auth
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.studios.schemas import (
    PaymentMethodConfigResponse,
    PaymentMethodConfigUpdateRequest,
    StudioOnboardingRequest,
    StudioResponse,
    StudioUpdateSettingsRequest,
)
from app.domains.core.studios.service import (
    get_current_studio_details,
    list_studio_payment_methods,
    onboard_studio_public,
    update_current_studio_settings,
    update_studio_payment_method,
)

router = APIRouter(prefix="/studios", tags=["Studios"])


@router.post(
    "/onboarding",
    response_model=StudioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth("onboarding"))],
)
async def create_studio_onboarding(
    payload: StudioOnboardingRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StudioResponse:
    studio = await onboard_studio_public(db, payload, request=request)
    return StudioResponse.model_validate(studio)


@router.get("/current", response_model=StudioResponse)
async def read_current_studio(
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> StudioResponse:
    studio = await get_current_studio_details(db, tenant)
    return StudioResponse.model_validate(studio)


@router.patch("/current", response_model=StudioResponse)
async def patch_current_studio(
    payload: StudioUpdateSettingsRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> StudioResponse:
    studio = await update_current_studio_settings(db, tenant, payload, request=request)
    return StudioResponse.model_validate(studio)


@router.get(
    "/current/payment-methods",
    response_model=list[PaymentMethodConfigResponse],
)
async def read_payment_methods(
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentMethodConfigResponse]:
    configs = await list_studio_payment_methods(db, tenant)
    return [PaymentMethodConfigResponse.model_validate(c) for c in configs]


@router.put(
    "/current/payment-methods/{config_id}",
    response_model=PaymentMethodConfigResponse,
)
async def update_payment_method_config(
    config_id: uuid.UUID,
    payload: PaymentMethodConfigUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodConfigResponse:
    updated = await update_studio_payment_method(
        db, tenant, config_id, payload, request=request
    )
    return PaymentMethodConfigResponse.model_validate(updated)
