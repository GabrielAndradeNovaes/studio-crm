from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import (
    AppointmentStatus,
    AuditAction,
    CashFlowDirection,
    DepositStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    StudioRole,
)
from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
)
from app.core.rbac import TenantContext
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import (
    calculate_age_in_timezone,
    studio_date_range_to_utc,
    timestamp_to_studio_date,
    utcnow,
)
from app.domains.core.appointments.models import Appointment
from app.domains.core.appointments.repository import AppointmentRepository
from app.domains.core.appointments.schemas import (
    AppointmentCreateRequest,
    AppointmentDepositRefundRequest,
    AppointmentDepositRequest,
    AppointmentResponse,
    AppointmentUpdateRequest,
)
from app.domains.core.clients.models import Client
from app.domains.core.clients.repository import ClientRepository
from app.domains.core.finance.models import FinancialTransaction, Payment
from app.domains.core.finance.money import compute_payment_fee_and_net, money
from app.domains.core.finance.repository import (
    FinancialTransactionRepository,
    PaymentRepository,
)
from app.domains.core.studios.repository import PaymentMethodConfigRepository
from app.domains.core.users.models import User
from app.domains.core.users.repository import StudioMembershipRepository
from app.domains.piercing.services.models import PiercingService
from app.domains.piercing.services.repository import PiercingServiceRepository


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _assert_minor_client_ready_for_attendance(
    client: Client, *, studio_timezone: str
) -> bool:
    _, is_minor = calculate_age_in_timezone(client.birth_date, studio_timezone)
    if is_minor:
        if (
            not client.guardian_name
            or not client.guardian_cpf
            or not client.guardian_whatsapp
        ):
            raise DomainValidationError(
                detail=(
                    "Atendimento bloqueado: cliente menor de 18 anos sem dados completos "
                    "do responsável legal (nome, CPF e WhatsApp)."
                ),
                code="MINOR_GUARDIAN_REQUIRED",
            )
    return is_minor


async def _validate_active_professional(
    session: AsyncSession, studio_id: uuid.UUID, professional_id: uuid.UUID
) -> User:
    membership_repo = StudioMembershipRepository(session, studio_id)
    membership = await membership_repo.get_by_user_id(professional_id)
    if membership is None or not membership.is_active:
        raise DomainValidationError(
            detail="O profissional informado não possui vínculo ativo neste estúdio.",
            code="INVALID_PROFESSIONAL",
        )
    with bypass_tenant_filter():
        user = (
            await session.execute(
                sa.select(User).where(
                    User.id == professional_id,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
    if user is None:
        raise DomainValidationError(
            detail="Profissional inativo ou inexistente.",
            code="INVALID_PROFESSIONAL",
        )
    return user


async def _enrich_appointments(
    session: AsyncSession,
    tenant: TenantContext,
    appointments: list[Appointment],
) -> list[AppointmentResponse]:
    if not appointments:
        return []

    client_ids = {a.client_id for a in appointments}
    prof_ids = {a.professional_id for a in appointments}
    service_ids = {a.service_id for a in appointments if a.service_id is not None}

    clients_rows = (
        await session.execute(
            sa.select(Client).where(
                Client.studio_id == tenant.studio_id,
                Client.id.in_(client_ids),
            )
        )
    ).scalars().all()
    clients_map = {c.id: c for c in clients_rows}

    with bypass_tenant_filter():
        users_rows = (
            await session.execute(sa.select(User).where(User.id.in_(prof_ids)))
        ).scalars().all()
    users_map = {u.id: u for u in users_rows}

    services_map: dict[uuid.UUID, PiercingService] = {}
    if service_ids:
        svc_rows = (
            await session.execute(
                sa.select(PiercingService).where(
                    PiercingService.studio_id == tenant.studio_id,
                    PiercingService.id.in_(service_ids),
                )
            )
        ).scalars().all()
        services_map = {s.id: s for s in svc_rows}

    enriched: list[AppointmentResponse] = []
    for appt in appointments:
        client = clients_map.get(appt.client_id)
        prof = users_map.get(appt.professional_id)
        svc = services_map.get(appt.service_id) if appt.service_id else None
        is_minor = (
            calculate_age_in_timezone(client.birth_date, tenant.timezone)[1]
            if client
            else False
        )
        enriched.append(
            AppointmentResponse(
                id=appt.id,
                studio_id=appt.studio_id,
                client_id=appt.client_id,
                client_name=client.full_name if client else "Cliente",
                client_whatsapp=client.whatsapp if client else "",
                client_is_minor=is_minor,
                professional_id=appt.professional_id,
                professional_name=prof.name if prof else "Profissional",
                module=appt.module,
                service_id=appt.service_id,
                service_name=svc.name if svc else None,
                start_at=_ensure_utc(appt.start_at),
                end_at=_ensure_utc(appt.end_at),
                status=appt.status,
                notes=appt.notes,
                deposit_amount=appt.deposit_amount,
                deposit_payment_method=appt.deposit_payment_method,
                deposit_status=appt.deposit_status,
                deposit_paid_at=(
                    _ensure_utc(appt.deposit_paid_at) if appt.deposit_paid_at else None
                ),
                created_at=_ensure_utc(appt.created_at),
                updated_at=_ensure_utc(appt.updated_at),
            )
        )
    return enriched


async def list_appointments(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    professional_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    status: AppointmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AppointmentResponse]:
    if tenant.role == StudioRole.PROFESSIONAL:
        if professional_id is not None and professional_id != tenant.user_id:
            raise ForbiddenError(
                detail="Profissionais só podem visualizar a própria agenda.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )
        effective_prof_id: uuid.UUID | None = tenant.user_id
    else:
        effective_prof_id = professional_id

    start_from_utc: datetime | None = None
    start_to_utc: datetime | None = None
    if date_from and date_to:
        start_from_utc, start_to_utc = studio_date_range_to_utc(
            date_from, date_to, tenant.timezone
        )
    elif date_from:
        start_from_utc, _ = studio_date_range_to_utc(
            date_from, date_from, tenant.timezone
        )
    elif date_to:
        _, start_to_utc = studio_date_range_to_utc(date_to, date_to, tenant.timezone)

    repo = AppointmentRepository(session, tenant.studio_id)
    rows = list(
        await repo.search(
            professional_id=effective_prof_id,
            client_id=client_id,
            status=status,
            start_from=start_from_utc,
            start_to=start_to_utc,
        )
    )
    return await _enrich_appointments(session, tenant, rows)


async def get_appointment_detail(
    session: AsyncSession,
    tenant: TenantContext,
    appointment_id: uuid.UUID,
) -> AppointmentResponse:
    repo = AppointmentRepository(session, tenant.studio_id)
    appt = await repo.get_by_id_or_404(
        appointment_id, detail="Agendamento não encontrado."
    )
    if (
        tenant.role == StudioRole.PROFESSIONAL
        and appt.professional_id != tenant.user_id
    ):
        raise ForbiddenError(
            detail="Profissionais só podem acessar os próprios agendamentos.",
            code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
        )
    return (await _enrich_appointments(session, tenant, [appt]))[0]


async def create_appointment(
    session: AsyncSession,
    tenant: TenantContext,
    payload: AppointmentCreateRequest,
    *,
    request: Request | None = None,
) -> AppointmentResponse:
    module_clean = payload.module.strip().lower()
    if module_clean not in tenant.enabled_modules:
        raise ForbiddenError(
            detail=f"O módulo '{module_clean}' não está habilitado para este estúdio.",
            code="MODULE_DISABLED",
        )

    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id_or_404(
        payload.client_id, detail="Cliente não encontrado."
    )
    _assert_minor_client_ready_for_attendance(
        client, studio_timezone=tenant.timezone
    )
    await _validate_active_professional(
        session, tenant.studio_id, payload.professional_id
    )

    service_duration = 30
    if payload.service_id is not None:
        svc_repo = PiercingServiceRepository(session, tenant.studio_id)
        svc = await svc_repo.get_by_id_or_404(
            payload.service_id, detail="Serviço de perfuração não encontrado."
        )
        service_duration = svc.duration_minutes

    end_at = payload.end_at or (payload.start_at + timedelta(minutes=service_duration))
    if end_at <= payload.start_at:
        raise DomainValidationError(
            detail="O horário de término deve ser posterior ao horário de início.",
            code="INVALID_APPOINTMENT_INTERVAL",
        )

    repo = AppointmentRepository(session, tenant.studio_id)
    if payload.status not in {AppointmentStatus.CANCELADO, AppointmentStatus.FALTOU}:
        conflict = await repo.has_overlapping_appointment(
            professional_id=payload.professional_id,
            start_at=payload.start_at,
            end_at=end_at,
        )
        if conflict:
            raise ConflictError(
                detail="Conflito de agenda: o profissional já possui atendimento neste intervalo de horário.",
                code="APPOINTMENT_TIME_CONFLICT",
            )

    appt = Appointment(
        studio_id=tenant.studio_id,
        client_id=client.id,
        professional_id=payload.professional_id,
        module=module_clean,
        service_id=payload.service_id,
        start_at=payload.start_at,
        end_at=end_at,
        status=payload.status,
        notes=payload.notes.strip() if payload.notes else None,
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )
    await repo.add(appt)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="appointments",
        entity_id=appt.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "client_id": str(appt.client_id),
            "professional_id": str(appt.professional_id),
            "start_at": appt.start_at.isoformat(),
            "status": appt.status.value,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(appt)
    return (await _enrich_appointments(session, tenant, [appt]))[0]


async def update_appointment(
    session: AsyncSession,
    tenant: TenantContext,
    appointment_id: uuid.UUID,
    payload: AppointmentUpdateRequest,
    *,
    request: Request | None = None,
) -> AppointmentResponse:
    repo = AppointmentRepository(session, tenant.studio_id)
    existing = await repo.get_by_id_or_404(
        appointment_id, detail="Agendamento não encontrado."
    )

    if tenant.role == StudioRole.PROFESSIONAL:
        if existing.professional_id != tenant.user_id:
            raise ForbiddenError(
                detail="Profissionais só podem atualizar os próprios agendamentos.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )
        raw_changes = payload.model_dump(exclude_unset=True)
        disallowed = set(raw_changes.keys()) - {"status", "notes"}
        if disallowed:
            raise ForbiddenError(
                detail="Profissionais só podem alterar o status e as observações dos próprios agendamentos.",
                code="INSUFFICIENT_ROLE",
            )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return (await _enrich_appointments(session, tenant, [existing]))[0]

    target_prof_id = changes.get("professional_id", existing.professional_id)
    if "professional_id" in changes:
        await _validate_active_professional(session, tenant.studio_id, target_prof_id)

    if "service_id" in changes and changes["service_id"] is not None:
        svc_repo = PiercingServiceRepository(session, tenant.studio_id)
        await svc_repo.get_by_id_or_404(
            changes["service_id"], detail="Serviço não encontrado."
        )

    target_start = changes.get("start_at", _ensure_utc(existing.start_at))
    target_end = changes.get("end_at", _ensure_utc(existing.end_at))
    if target_end <= target_start:
        raise DomainValidationError(
            detail="O horário de término deve ser posterior ao horário de início.",
            code="INVALID_APPOINTMENT_INTERVAL",
        )

    target_status = changes.get("status", existing.status)
    if target_status in {
        AppointmentStatus.CONFIRMADO,
        AppointmentStatus.EM_ATENDIMENTO,
    }:
        client_repo = ClientRepository(session, tenant.studio_id)
        client = await client_repo.get_by_id_or_404(existing.client_id)
        _assert_minor_client_ready_for_attendance(
            client, studio_timezone=tenant.timezone
        )

    if target_status not in {AppointmentStatus.CANCELADO, AppointmentStatus.FALTOU}:
        conflict = await repo.has_overlapping_appointment(
            professional_id=target_prof_id,
            start_at=target_start,
            end_at=target_end,
            exclude_appointment_id=existing.id,
        )
        if conflict:
            raise ConflictError(
                detail="Conflito de agenda: o profissional já possui atendimento neste intervalo de horário.",
                code="APPOINTMENT_TIME_CONFLICT",
            )

    if "notes" in changes and changes["notes"] is not None:
        changes["notes"] = changes["notes"].strip() or None
    changes["updated_by"] = tenant.user_id

    updated = await repo.update_by_id(existing.id, changes)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="appointments",
        entity_id=existing.id,
        action=AuditAction.UPDATE,
        metadata_diff={
            k: (v.value if hasattr(v, "value") else str(v))
            for k, v in changes.items()
            if k != "updated_by"
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return (await _enrich_appointments(session, tenant, [updated]))[0]


async def register_appointment_deposit(
    session: AsyncSession,
    tenant: TenantContext,
    appointment_id: uuid.UUID,
    payload: AppointmentDepositRequest,
    *,
    request: Request | None = None,
) -> AppointmentResponse:
    repo = AppointmentRepository(session, tenant.studio_id)
    appt = await repo.get_by_id_for_update_or_404(appointment_id)

    if appt.deposit_status in {DepositStatus.PAID, DepositStatus.APPLIED_TO_SALE}:
        raise ConflictError(
            detail="O sinal deste agendamento já foi registrado anteriormente.",
            code="DEPOSIT_ALREADY_PAID",
        )
    if appt.status in {AppointmentStatus.CANCELADO, AppointmentStatus.FALTOU}:
        raise DomainValidationError(
            detail="Não é possível registrar sinal para um agendamento cancelado ou com falta.",
            code="INVALID_APPOINTMENT_STATE",
        )

    pm_repo = PaymentMethodConfigRepository(session, tenant.studio_id)
    pm_configs = await pm_repo.list_ordered()
    active_pm = next(
        (
            pm
            for pm in pm_configs
            if pm.method == payload.payment_method and pm.is_active
        ),
        None,
    )
    if active_pm is None:
        raise DomainValidationError(
            detail=f"O meio de pagamento '{payload.payment_method.value}' não está ativo neste estúdio.",
            code="PAYMENT_METHOD_INACTIVE",
        )

    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id_or_404(appt.client_id)

    gross_amount = money(payload.amount)
    fee_amount, net_amount = compute_payment_fee_and_net(
        gross_amount=gross_amount,
        fee_percentage=active_pm.fee_percentage,
        fixed_fee=active_pm.fixed_fee,
    )
    paid_at = payload.paid_at or utcnow()
    comp_date = timestamp_to_studio_date(paid_at, tenant.timezone)

    pay_repo = PaymentRepository(session, tenant.studio_id)
    payment = await pay_repo.add(
        Payment(
            studio_id=tenant.studio_id,
            sale_id=None,
            appointment_id=appt.id,
            method=payload.payment_method,
            is_deposit=True,
            gross_amount=gross_amount,
            fee_percentage_snapshot=active_pm.fee_percentage,
            fixed_fee_snapshot=active_pm.fixed_fee,
            fee_amount=fee_amount,
            net_amount=net_amount,
            paid_at=paid_at,
            created_by=tenant.user_id,
        )
    )

    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    await tx_repo.add(
        FinancialTransaction(
            studio_id=tenant.studio_id,
            type=FinancialTransactionType.INCOME,
            category=FinancialTransactionCategory.APPOINTMENT_DEPOSIT,
            cash_flow_direction=CashFlowDirection.INFLOW,
            payment_method=payload.payment_method,
            description=f"Sinal de agendamento — {client.full_name}",
            gross_amount=gross_amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            competence_date=comp_date,
            paid_at=paid_at,
            reference_payment_id=payment.id,
            reference_appointment_id=appt.id,
            created_by=tenant.user_id,
        )
    )

    updated = await repo.update_by_id(
        appt.id,
        {
            "deposit_amount": gross_amount,
            "deposit_payment_method": payload.payment_method,
            "deposit_status": DepositStatus.PAID,
            "deposit_paid_at": paid_at,
            "updated_by": tenant.user_id,
        },
    )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="appointments",
        entity_id=appt.id,
        action=AuditAction.DEPOSIT_RECEIVED,
        metadata_diff={
            "deposit_amount": str(gross_amount),
            "fee_amount": str(fee_amount),
            "net_amount": str(net_amount),
            "deposit_payment_method": payload.payment_method.value,
            "competence_date": comp_date.isoformat(),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return (await _enrich_appointments(session, tenant, [updated]))[0]


async def refund_appointment_deposit(
    session: AsyncSession,
    tenant: TenantContext,
    appointment_id: uuid.UUID,
    payload: AppointmentDepositRefundRequest,
    *,
    request: Request | None = None,
) -> AppointmentResponse:
    repo = AppointmentRepository(session, tenant.studio_id)
    appt = await repo.get_by_id_for_update_or_404(appointment_id)

    if appt.deposit_status == DepositStatus.REFUNDED:
        raise ConflictError(
            detail="O sinal deste agendamento já foi estornado.",
            code="DEPOSIT_ALREADY_REFUNDED",
        )
    if appt.deposit_status == DepositStatus.APPLIED_TO_SALE:
        raise ConflictError(
            detail="Este sinal já foi abatido em uma venda concluída; utilize o estorno da venda.",
            code="DEPOSIT_APPLIED_TO_SALE",
        )
    if appt.deposit_status != DepositStatus.PAID or appt.deposit_amount <= 0:
        raise DomainValidationError(
            detail="Este agendamento não possui sinal pago pendente para estorno.",
            code="DEPOSIT_NOT_REFUNDABLE",
        )

    orig_tx = (
        await session.execute(
            sa.select(FinancialTransaction)
            .where(
                FinancialTransaction.studio_id == tenant.studio_id,
                FinancialTransaction.reference_appointment_id == appt.id,
                FinancialTransaction.category
                == FinancialTransactionCategory.APPOINTMENT_DEPOSIT,
            )
            .order_by(FinancialTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    now = utcnow()
    comp_date = timestamp_to_studio_date(now, tenant.timezone)
    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)

    reversed_id: uuid.UUID | None = None
    if orig_tx is not None and not await tx_repo.has_reversal(orig_tx.id):
        reversed_id = orig_tx.id

    refund_amt = money(appt.deposit_amount)
    await tx_repo.add(
        FinancialTransaction(
            studio_id=tenant.studio_id,
            type=FinancialTransactionType.REVERSAL,
            category=FinancialTransactionCategory.REFUND_OUTFLOW,
            cash_flow_direction=CashFlowDirection.OUTFLOW,
            payment_method=appt.deposit_payment_method,
            description=f"Estorno de sinal de agendamento — {payload.reason.strip()}",
            gross_amount=refund_amt,
            fee_amount=money("0.00"),
            net_amount=refund_amt,
            competence_date=comp_date,
            paid_at=now,
            reference_appointment_id=appt.id,
            reversed_transaction_id=reversed_id,
            created_by=tenant.user_id,
        )
    )

    next_status = (
        appt.status
        if appt.status in {AppointmentStatus.CANCELADO, AppointmentStatus.FALTOU}
        else AppointmentStatus.CANCELADO
    )
    updated = await repo.update_by_id(
        appt.id,
        {
            "deposit_status": DepositStatus.REFUNDED,
            "status": next_status,
            "updated_by": tenant.user_id,
        },
    )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="appointments",
        entity_id=appt.id,
        action=AuditAction.DEPOSIT_REFUNDED,
        metadata_diff={
            "refunded_amount": str(refund_amt),
            "reason": payload.reason.strip(),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return (await _enrich_appointments(session, tenant, [updated]))[0]


async def soft_delete_appointment(
    session: AsyncSession,
    tenant: TenantContext,
    appointment_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    repo = AppointmentRepository(session, tenant.studio_id)
    appt = await repo.get_by_id_or_404(
        appointment_id, detail="Agendamento não encontrado."
    )
    await repo.soft_delete_by_id(appt.id, actor_user_id=tenant.user_id)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="appointments",
        entity_id=appt.id,
        action=AuditAction.SOFT_DELETE,
        metadata_diff={"start_at": appt.start_at.isoformat()},
        request=request,
    )
    await session.commit()
