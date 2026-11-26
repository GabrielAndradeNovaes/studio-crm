from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import AuditAction
from app.core.rbac import TenantContext
from app.domains.piercing.services.models import PiercingService
from app.domains.piercing.services.repository import PiercingServiceRepository
from app.domains.piercing.services.schemas import (
    PiercingServiceCreateRequest,
    PiercingServiceUpdateRequest,
)


async def list_piercing_services(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    q: str | None = None,
    anatomical_site: str | None = None,
    active_only: bool = False,
) -> list[PiercingService]:
    repo = PiercingServiceRepository(session, tenant.studio_id)
    return list(
        await repo.search(q=q, anatomical_site=anatomical_site, active_only=active_only)
    )


async def get_piercing_service(
    session: AsyncSession, tenant: TenantContext, service_id: uuid.UUID
) -> PiercingService:
    repo = PiercingServiceRepository(session, tenant.studio_id)
    return await repo.get_by_id_or_404(
        service_id, detail="Serviço de perfuração não encontrado."
    )


async def create_piercing_service(
    session: AsyncSession,
    tenant: TenantContext,
    payload: PiercingServiceCreateRequest,
    *,
    request: Request | None = None,
) -> PiercingService:
    repo = PiercingServiceRepository(session, tenant.studio_id)
    service = PiercingService(
        studio_id=tenant.studio_id,
        name=payload.name.strip(),
        anatomical_site=payload.anatomical_site.strip(),
        duration_minutes=payload.duration_minutes,
        base_price=payload.base_price,
        return_days_downsize=payload.return_days_downsize,
        aftercare_instructions=(
            payload.aftercare_instructions.strip()
            if payload.aftercare_instructions
            else None
        ),
        is_active=payload.is_active,
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )
    await repo.add(service)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_services",
        entity_id=service.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "name": service.name,
            "anatomical_site": service.anatomical_site,
            "base_price": str(service.base_price),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(service)
    return service


async def update_piercing_service(
    session: AsyncSession,
    tenant: TenantContext,
    service_id: uuid.UUID,
    payload: PiercingServiceUpdateRequest,
    *,
    request: Request | None = None,
) -> PiercingService:
    repo = PiercingServiceRepository(session, tenant.studio_id)
    current = await repo.get_by_id_or_404(
        service_id, detail="Serviço de perfuração não encontrado."
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return current

    if "name" in changes and changes["name"]:
        changes["name"] = changes["name"].strip()
    if "anatomical_site" in changes and changes["anatomical_site"]:
        changes["anatomical_site"] = changes["anatomical_site"].strip()
    changes["updated_by"] = tenant.user_id

    updated = await repo.update_by_id(service_id, changes)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_services",
        entity_id=service_id,
        action=AuditAction.UPDATE,
        metadata_diff={
            k: str(v) for k, v in changes.items() if k != "updated_by"
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return updated


async def soft_delete_piercing_service(
    session: AsyncSession,
    tenant: TenantContext,
    service_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    repo = PiercingServiceRepository(session, tenant.studio_id)
    service = await repo.get_by_id_or_404(
        service_id, detail="Serviço de perfuração não encontrado."
    )
    await repo.soft_delete_by_id(service.id, actor_user_id=tenant.user_id)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_services",
        entity_id=service.id,
        action=AuditAction.SOFT_DELETE,
        metadata_diff={"name": service.name},
        request=request,
    )
    await session.commit()
