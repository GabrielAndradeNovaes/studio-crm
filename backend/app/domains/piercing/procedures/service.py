from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import AuditAction, StudioRole
from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError
from app.core.rbac import TenantContext
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import today_in_studio_timezone, utcnow
from app.domains.core.appointments.repository import AppointmentRepository
from app.domains.core.clients.models import Client
from app.domains.core.clients.repository import ClientRepository
from app.domains.core.users.models import User
from app.domains.core.users.repository import StudioMembershipRepository
from app.domains.piercing.inventory.models import PiercingProduct
from app.domains.piercing.inventory.repository import PiercingProductRepository
from app.domains.piercing.procedures.models import PiercingProcedure
from app.domains.piercing.procedures.repository import PiercingProcedureRepository
from app.domains.piercing.procedures.schemas import (
    CompleteDownsizeRequest,
    DownsizeWindowFilter,
    PiercingProcedureCreateRequest,
    PiercingProcedureResponse,
    PiercingProcedureUpdateRequest,
)
from app.domains.piercing.services.models import PiercingService
from app.domains.piercing.services.repository import PiercingServiceRepository


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _enrich_procedures(
    session: AsyncSession,
    tenant: TenantContext,
    procedures: list[PiercingProcedure],
) -> list[PiercingProcedureResponse]:
    if not procedures:
        return []

    today_local = today_in_studio_timezone(tenant.timezone)
    client_ids = {p.client_id for p in procedures}
    prof_ids = {p.professional_id for p in procedures}
    service_ids = {p.service_id for p in procedures}
    product_ids = {
        p.jewelry_product_id for p in procedures if p.jewelry_product_id is not None
    }

    clients_map = {
        c.id: c
        for c in (
            await session.execute(
                sa.select(Client).where(
                    Client.studio_id == tenant.studio_id, Client.id.in_(client_ids)
                )
            )
        )
        .scalars()
        .all()
    }
    with bypass_tenant_filter():
        users_map = {
            u.id: u
            for u in (
                await session.execute(sa.select(User).where(User.id.in_(prof_ids)))
            )
            .scalars()
            .all()
        }
    services_map = {
        s.id: s
        for s in (
            await session.execute(
                sa.select(PiercingService).where(
                    PiercingService.studio_id == tenant.studio_id,
                    PiercingService.id.in_(service_ids),
                )
            )
        )
        .scalars()
        .all()
    }
    products_map: dict[uuid.UUID, PiercingProduct] = {}
    if product_ids:
        products_map = {
            pr.id: pr
            for pr in (
                await session.execute(
                    sa.select(PiercingProduct).where(
                        PiercingProduct.studio_id == tenant.studio_id,
                        PiercingProduct.id.in_(product_ids),
                    )
                )
            )
            .scalars()
            .all()
        }

    enriched: list[PiercingProcedureResponse] = []
    for p in procedures:
        client = clients_map.get(p.client_id)
        prof = users_map.get(p.professional_id)
        svc = services_map.get(p.service_id)
        prod = products_map.get(p.jewelry_product_id) if p.jewelry_product_id else None

        days_until_due: int | None = None
        is_overdue = False
        if p.downsize_reminder_date is not None and p.downsize_completed_at is None:
            days_until_due = (p.downsize_reminder_date - today_local).days
            is_overdue = days_until_due < 0

        enriched.append(
            PiercingProcedureResponse(
                id=p.id,
                studio_id=p.studio_id,
                client_id=p.client_id,
                client_name=client.full_name if client else "Cliente",
                client_whatsapp=client.whatsapp if client else "",
                appointment_id=p.appointment_id,
                sale_id=p.sale_id,
                professional_id=p.professional_id,
                professional_name=prof.name if prof else "Profissional",
                service_id=p.service_id,
                service_name=svc.name if svc else "Serviço",
                jewelry_product_id=p.jewelry_product_id,
                jewelry_name=prod.name if prod else None,
                anatomical_site_detail=p.anatomical_site_detail,
                sterilization_lot=p.sterilization_lot,
                healing_notes=p.healing_notes,
                performed_at=_ensure_utc(p.performed_at),
                downsize_reminder_date=p.downsize_reminder_date,
                downsize_completed_at=(
                    _ensure_utc(p.downsize_completed_at)
                    if p.downsize_completed_at
                    else None
                ),
                is_overdue=is_overdue,
                days_until_due=days_until_due,
                created_at=_ensure_utc(p.created_at),
                updated_at=_ensure_utc(p.updated_at),
            )
        )
    return enriched


async def create_piercing_procedure(
    session: AsyncSession,
    tenant: TenantContext,
    payload: PiercingProcedureCreateRequest,
    *,
    request: Request | None = None,
) -> PiercingProcedureResponse:
    if tenant.role == StudioRole.PROFESSIONAL:
        if (
            payload.professional_id is not None
            and payload.professional_id != tenant.user_id
        ):
            raise ForbiddenError(
                detail="Profissionais só podem registrar procedimentos em seu próprio nome.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )
        effective_prof_id = tenant.user_id
    else:
        effective_prof_id = payload.professional_id or tenant.user_id

    membership_repo = StudioMembershipRepository(session, tenant.studio_id)
    membership = await membership_repo.get_by_user_id(effective_prof_id)
    if membership is None or not membership.is_active:
        raise DomainValidationError(
            detail="O profissional informado não possui vínculo ativo neste estúdio.",
            code="INVALID_PROFESSIONAL",
        )

    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id_or_404(
        payload.client_id, detail="Cliente não encontrado."
    )

    if payload.appointment_id is not None:
        appt_repo = AppointmentRepository(session, tenant.studio_id)
        appt = await appt_repo.get_by_id_or_404(
            payload.appointment_id, detail="Agendamento não encontrado."
        )
        if appt.client_id != client.id:
            raise DomainValidationError(
                detail="Agendamento não pertence ao cliente selecionado.",
                code="APPOINTMENT_CLIENT_MISMATCH",
            )

    svc_repo = PiercingServiceRepository(session, tenant.studio_id)
    service = await svc_repo.get_by_id_or_404(
        payload.service_id, detail="Serviço de perfuração não encontrado."
    )

    # IMPORTANTE: Apenas valida existência da joia no estúdio, SEM dar baixa em stock_quantity!
    if payload.jewelry_product_id is not None:
        prod_repo = PiercingProductRepository(session, tenant.studio_id)
        await prod_repo.get_by_id_or_404(
            payload.jewelry_product_id, detail="Joia não encontrada."
        )

    performed_at = payload.performed_at or utcnow()
    if payload.downsize_reminder_date is not None:
        reminder_date = payload.downsize_reminder_date
    elif (
        service.return_days_downsize is not None
        and service.return_days_downsize > 0
    ):
        studio_tz = ZoneInfo(tenant.timezone)
        local_performed_date = performed_at.astimezone(studio_tz).date()
        reminder_date = local_performed_date + timedelta(
            days=service.return_days_downsize
        )
    else:
        reminder_date = None

    proc_repo = PiercingProcedureRepository(session, tenant.studio_id)
    proc = PiercingProcedure(
        studio_id=tenant.studio_id,
        client_id=client.id,
        appointment_id=payload.appointment_id,
        professional_id=effective_prof_id,
        service_id=service.id,
        jewelry_product_id=payload.jewelry_product_id,
        anatomical_site_detail=payload.anatomical_site_detail.strip(),
        sterilization_lot=(
            payload.sterilization_lot.strip() if payload.sterilization_lot else None
        ),
        healing_notes=(
            payload.healing_notes.strip() if payload.healing_notes else None
        ),
        performed_at=performed_at,
        downsize_reminder_date=reminder_date,
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )
    await proc_repo.add(proc)

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_procedures",
        entity_id=proc.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "client_id": str(client.id),
            "service_id": str(service.id),
            "jewelry_product_id": (
                str(payload.jewelry_product_id) if payload.jewelry_product_id else None
            ),
            "downsize_reminder_date": (
                reminder_date.isoformat() if reminder_date else None
            ),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(proc)
    return (await _enrich_procedures(session, tenant, [proc]))[0]


async def list_piercing_procedures(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    client_id: uuid.UUID | None = None,
    professional_id: uuid.UUID | None = None,
    appointment_id: uuid.UUID | None = None,
) -> list[PiercingProcedureResponse]:
    if tenant.role == StudioRole.PROFESSIONAL:
        if professional_id is not None and professional_id != tenant.user_id:
            raise ForbiddenError(
                detail="Profissionais só podem listar os próprios procedimentos.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )
        effective_prof_id: uuid.UUID | None = (
            None if client_id is not None else tenant.user_id
        )
    else:
        effective_prof_id = professional_id

    repo = PiercingProcedureRepository(session, tenant.studio_id)
    rows = list(
        await repo.list_filtered(
            client_id=client_id,
            professional_id=effective_prof_id,
            appointment_id=appointment_id,
        )
    )
    return await _enrich_procedures(session, tenant, rows)


async def list_downsize_reminders(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    window: DownsizeWindowFilter = "next_7_days",
    professional_id: uuid.UUID | None = None,
) -> list[PiercingProcedureResponse]:
    if tenant.role == StudioRole.PROFESSIONAL:
        if professional_id is not None and professional_id != tenant.user_id:
            raise ForbiddenError(
                detail="Profissionais só podem visualizar os próprios retornos de downsize.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )
        effective_prof_id: uuid.UUID | None = tenant.user_id
    else:
        effective_prof_id = professional_id

    today_local = today_in_studio_timezone(tenant.timezone)
    repo = PiercingProcedureRepository(session, tenant.studio_id)

    if window == "overdue":
        rows = await repo.list_pending_downsizes(
            professional_id=effective_prof_id,
            strictly_before=today_local,
        )
    elif window == "next_7_days":
        rows = await repo.list_pending_downsizes(
            professional_id=effective_prof_id,
            due_from=today_local,
            due_before_or_on=today_local + timedelta(days=7),
        )
    elif window == "next_30_days":
        rows = await repo.list_pending_downsizes(
            professional_id=effective_prof_id,
            due_from=today_local,
            due_before_or_on=today_local + timedelta(days=30),
        )
    else:
        rows = await repo.list_pending_downsizes(professional_id=effective_prof_id)

    return await _enrich_procedures(session, tenant, list(rows))


async def update_piercing_procedure(
    session: AsyncSession,
    tenant: TenantContext,
    procedure_id: uuid.UUID,
    payload: PiercingProcedureUpdateRequest,
    *,
    request: Request | None = None,
) -> PiercingProcedureResponse:
    repo = PiercingProcedureRepository(session, tenant.studio_id)
    existing = await repo.get_by_id_or_404(
        procedure_id, detail="Procedimento não encontrado."
    )
    if (
        tenant.role == StudioRole.PROFESSIONAL
        and existing.professional_id != tenant.user_id
    ):
        raise ForbiddenError(
            detail="Profissionais só podem editar os próprios procedimentos.",
            code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return (await _enrich_procedures(session, tenant, [existing]))[0]

    if "jewelry_product_id" in changes and changes["jewelry_product_id"] is not None:
        prod_repo = PiercingProductRepository(session, tenant.studio_id)
        await prod_repo.get_by_id_or_404(
            changes["jewelry_product_id"], detail="Joia não encontrada."
        )

    changes["updated_by"] = tenant.user_id
    updated = await repo.update_by_id(existing.id, changes)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_procedures",
        entity_id=existing.id,
        action=AuditAction.UPDATE,
        metadata_diff={
            k: str(v) for k, v in changes.items() if k != "updated_by"
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return (await _enrich_procedures(session, tenant, [updated]))[0]


async def complete_downsize_return(
    session: AsyncSession,
    tenant: TenantContext,
    procedure_id: uuid.UUID,
    payload: CompleteDownsizeRequest,
    *,
    request: Request | None = None,
) -> PiercingProcedureResponse:
    repo = PiercingProcedureRepository(session, tenant.studio_id)
    existing = await repo.get_by_id_or_404(
        procedure_id, detail="Procedimento não encontrado."
    )
    if (
        tenant.role == StudioRole.PROFESSIONAL
        and existing.professional_id != tenant.user_id
    ):
        raise ForbiddenError(
            detail="Profissionais só podem concluir downsize dos próprios procedimentos.",
            code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
        )
    if existing.downsize_completed_at is not None:
        raise ConflictError(
            detail="O retorno de downsize deste procedimento já foi concluído.",
            code="DOWNSIZE_ALREADY_COMPLETED",
        )

    now = utcnow()
    notes_merged = existing.healing_notes or ""
    if payload.notes and payload.notes.strip():
        addition = f"[Downsize {now.strftime('%d/%m/%Y')}]: {payload.notes.strip()}"
        notes_merged = f"{notes_merged}\n{addition}".strip() if notes_merged else addition

    updated = await repo.update_by_id(
        existing.id,
        {
            "downsize_completed_at": now,
            "healing_notes": notes_merged or None,
            "updated_by": tenant.user_id,
        },
    )
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_procedures",
        entity_id=existing.id,
        action=AuditAction.UPDATE,
        metadata_diff={"downsize_completed_at": now.isoformat()},
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return (await _enrich_procedures(session, tenant, [updated]))[0]
