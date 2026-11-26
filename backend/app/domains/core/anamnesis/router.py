from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import StudioRole
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.anamnesis.schemas import (
    AnamnesisRecordCreateRequest,
    AnamnesisRecordDetailResponse,
    AnamnesisRecordSummaryResponse,
    AnamnesisTemplateResponse,
    AnamnesisTemplateUpsertRequest,
    CreatePublicAnamnesisLinkRequest,
    PublicAnamnesisLinkCreatedResponse,
)
from app.domains.core.anamnesis.service import (
    create_internal_anamnesis_record,
    create_new_template_version,
    create_public_anamnesis_link,
    get_anamnesis_record_detail_audited,
    list_anamnesis_records,
    list_templates,
    reject_immutable_anamnesis_mutation,
    update_template_versioned,
)

router = APIRouter(prefix="/anamnesis", tags=["Anamnesis & Consent (LGPD)"])


@router.get("/templates", response_model=list[AnamnesisTemplateResponse])
async def list_templates_endpoint(
    module: str | None = Query(default=None, max_length=30),
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[AnamnesisTemplateResponse]:
    rows = await list_templates(db, tenant, module=module)
    return [AnamnesisTemplateResponse.model_validate(r) for r in rows]


@router.post(
    "/templates",
    response_model=AnamnesisTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_endpoint(
    payload: AnamnesisTemplateUpsertRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> AnamnesisTemplateResponse:
    tpl = await create_new_template_version(db, tenant, payload, request=request)
    return AnamnesisTemplateResponse.model_validate(tpl)


@router.put("/templates/{template_id}", response_model=AnamnesisTemplateResponse)
@router.patch("/templates/{template_id}", response_model=AnamnesisTemplateResponse)
async def update_template_endpoint(
    template_id: uuid.UUID,
    payload: AnamnesisTemplateUpsertRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> AnamnesisTemplateResponse:
    tpl = await update_template_versioned(
        db, tenant, template_id, payload, request=request
    )
    return AnamnesisTemplateResponse.model_validate(tpl)


@router.get("/records", response_model=list[AnamnesisRecordSummaryResponse])
async def list_records_endpoint(
    client_id: uuid.UUID | None = Query(default=None),
    appointment_id: uuid.UUID | None = Query(default=None),
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[AnamnesisRecordSummaryResponse]:
    return await list_anamnesis_records(
        db, tenant, client_id=client_id, appointment_id=appointment_id
    )


@router.get("/records/{record_id}", response_model=AnamnesisRecordDetailResponse)
async def get_record_detail_endpoint(
    record_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> AnamnesisRecordDetailResponse:
    return await get_anamnesis_record_detail_audited(
        db, tenant, record_id, request=request
    )


@router.post(
    "/records",
    response_model=AnamnesisRecordDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_record_endpoint(
    payload: AnamnesisRecordCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> AnamnesisRecordDetailResponse:
    return await create_internal_anamnesis_record(
        db, tenant, payload, request=request
    )


@router.patch("/records/{record_id}")
@router.put("/records/{record_id}")
@router.delete("/records/{record_id}")
async def block_record_mutation_endpoint(
    record_id: uuid.UUID,
    _body: dict[str, Any] | None = None,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    await reject_immutable_anamnesis_mutation(db, tenant, record_id)


@router.post(
    "/public-links",
    response_model=PublicAnamnesisLinkCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_public_link_endpoint(
    payload: CreatePublicAnamnesisLinkRequest,
    request: Request,
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> PublicAnamnesisLinkCreatedResponse:
    return await create_public_anamnesis_link(
        db, tenant, payload, request=request
    )
