from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import (
    AppointmentStatus,
    AuditAction,
    CashFlowDirection,
    CommissionStatus,
    DepositStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    InventoryMovementType,
    SaleItemKind,
    SaleStatus,
    StudioRole,
)
from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from app.core.rbac import TenantContext
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import timestamp_to_studio_date, utcnow
from app.domains.core.appointments.models import Appointment
from app.domains.core.appointments.repository import AppointmentRepository
from app.domains.core.clients.models import Client
from app.domains.core.clients.repository import ClientRepository
from app.domains.core.finance.models import (
    Commission,
    FinancialTransaction,
    Payment,
    Sale,
    SaleItem,
)
from app.domains.core.finance.money import (
    HUNDRED,
    ZERO,
    compute_payment_fee_and_net,
    money,
)
from app.domains.core.finance.repository import (
    CommissionRepository,
    FinancialTransactionRepository,
    PaymentRepository,
    SaleItemRepository,
    SaleRepository,
)
from app.domains.core.finance.schemas import (
    SaleCheckoutRequest,
    SaleItemOwnerResponse,
    SaleItemStaffResponse,
    SaleOwnerResponse,
    SalePaymentResponse,
    SaleRefundRequest,
    SaleStaffResponse,
)
from app.domains.core.studios.repository import PaymentMethodConfigRepository
from app.domains.core.users.models import StudioMembership, User
from app.domains.core.users.repository import StudioMembershipRepository
from app.domains.piercing.inventory.models import InventoryMovement, PiercingProduct
from app.domains.piercing.inventory.repository import (
    InventoryMovementRepository,
    PiercingProductRepository,
)
from app.domains.piercing.procedures.models import PiercingProcedure
from app.domains.piercing.services.models import PiercingService
from app.domains.piercing.services.repository import PiercingServiceRepository


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def serialize_sales_for_role(
    session: AsyncSession,
    tenant: TenantContext,
    sales: list[Sale],
    *,
    force_staff_view: bool = False,
) -> list[SaleOwnerResponse | SaleStaffResponse]:
    if not sales:
        return []

    sale_ids = [s.id for s in sales]
    client_ids = {s.client_id for s in sales if s.client_id is not None}
    prof_ids = {s.professional_id for s in sales if s.professional_id is not None}
    appt_ids = {s.appointment_id for s in sales if s.appointment_id is not None}

    item_repo = SaleItemRepository(session, tenant.studio_id)
    all_items = await item_repo.list_by_sale_ids(sale_ids)
    items_by_sale: dict[uuid.UUID, list[SaleItem]] = defaultdict(list)
    for it in all_items:
        items_by_sale[it.sale_id].append(it)

    pay_repo = PaymentRepository(session, tenant.studio_id)
    checkout_payments = await pay_repo.list_by_sale_ids(sale_ids)
    payments_by_sale: dict[uuid.UUID, list[Payment]] = defaultdict(list)
    for p in checkout_payments:
        if p.sale_id:
            payments_by_sale[p.sale_id].append(p)

    # Inclui pagamento do sinal aplicado (quando houver) na visualização da venda
    deposit_by_appt: dict[uuid.UUID, Payment] = {}
    if appt_ids:
        dep_rows = (
            await session.execute(
                sa.select(Payment).where(
                    Payment.studio_id == tenant.studio_id,
                    Payment.appointment_id.in_(appt_ids),
                    Payment.is_deposit.is_(True),
                )
            )
        ).scalars().all()
        for dp in dep_rows:
            if dp.appointment_id:
                deposit_by_appt[dp.appointment_id] = dp

    clients_map: dict[uuid.UUID, str] = {}
    if client_ids:
        c_rows = (
            await session.execute(
                sa.select(Client).where(
                    Client.studio_id == tenant.studio_id,
                    Client.id.in_(client_ids),
                )
            )
        ).scalars().all()
        clients_map = {c.id: c.full_name for c in c_rows}

    users_map: dict[uuid.UUID, str] = {}
    if prof_ids:
        with bypass_tenant_filter():
            u_rows = (
                await session.execute(sa.select(User).where(User.id.in_(prof_ids)))
            ).scalars().all()
        users_map = {u.id: u.name for u in u_rows}

    is_owner_dto = tenant.role == StudioRole.OWNER and not force_staff_view
    output: list[SaleOwnerResponse | SaleStaffResponse] = []

    for s in sales:
        s_items = items_by_sale.get(s.id, [])
        s_payments = list(payments_by_sale.get(s.id, []))
        if (
            s.appointment_id
            and s.deposit_deducted_amount > ZERO
            and s.appointment_id in deposit_by_appt
        ):
            s_payments.insert(0, deposit_by_appt[s.appointment_id])

        pay_dtos = [
            SalePaymentResponse(
                id=p.id,
                method=p.method,
                is_deposit=p.is_deposit,
                gross_amount=p.gross_amount,
                fee_percentage_snapshot=p.fee_percentage_snapshot,
                fee_amount=p.fee_amount,
                net_amount=p.net_amount,
                paid_at=_ensure_utc(p.paid_at),
            )
            for p in s_payments
        ]

        base_fields = {
            "id": s.id,
            "studio_id": s.studio_id,
            "client_id": s.client_id,
            "client_name": clients_map.get(s.client_id) if s.client_id else None,
            "appointment_id": s.appointment_id,
            "professional_id": s.professional_id,
            "professional_name": (
                users_map.get(s.professional_id) if s.professional_id else None
            ),
            "status": s.status,
            "competence_date": s.competence_date,
            "subtotal_amount": s.subtotal_amount,
            "discount_amount": s.discount_amount,
            "deposit_deducted_amount": s.deposit_deducted_amount,
            "total_due_amount": s.total_due_amount,
            "notes": s.notes,
            "refunded_at": _ensure_utc(s.refunded_at) if s.refunded_at else None,
            "refund_reason": s.refund_reason,
            "created_at": _ensure_utc(s.created_at),
            "payments": pay_dtos,
        }

        if is_owner_dto:
            owner_items = [
                SaleItemOwnerResponse(
                    id=it.id,
                    item_kind=it.item_kind,
                    service_id=it.service_id,
                    product_id=it.product_id,
                    professional_id=it.professional_id,
                    description_snapshot=it.description_snapshot,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    unit_cost_snapshot=it.unit_cost_snapshot,
                    discount_amount=it.discount_amount,
                    total_item_amount=it.total_item_amount,
                )
                for it in s_items
            ]
            output.append(
                SaleOwnerResponse(
                    **base_fields,
                    total_cost_snapshot=s.total_cost_snapshot,
                    items=owner_items,
                )
            )
        else:
            staff_items = [
                SaleItemStaffResponse(
                    id=it.id,
                    item_kind=it.item_kind,
                    service_id=it.service_id,
                    product_id=it.product_id,
                    professional_id=it.professional_id,
                    description_snapshot=it.description_snapshot,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    discount_amount=it.discount_amount,
                    total_item_amount=it.total_item_amount,
                )
                for it in s_items
            ]
            output.append(SaleStaffResponse(**base_fields, items=staff_items))

    return output


async def checkout_pos_sale(
    session: AsyncSession,
    tenant: TenantContext,
    payload: SaleCheckoutRequest,
    *,
    request: Request | None = None,
) -> SaleOwnerResponse | SaleStaffResponse:
    sold_at = payload.sold_at or utcnow()
    comp_date = timestamp_to_studio_date(sold_at, tenant.timezone)

    # 1. Valida e bloqueia Agendamento (se vinculado) para evitar abatimento duplo de sinal
    appt: Appointment | None = None
    deposit_deducted = ZERO
    effective_client_id = payload.client_id
    effective_sale_prof_id = payload.professional_id

    if payload.appointment_id is not None:
        appt_repo = AppointmentRepository(session, tenant.studio_id)
        appt = await appt_repo.get_by_id_for_update_or_404(payload.appointment_id)

        existing_completed_sale = (
            await session.execute(
                sa.select(Sale.id)
                .where(
                    Sale.studio_id == tenant.studio_id,
                    Sale.appointment_id == appt.id,
                    Sale.status == SaleStatus.COMPLETED,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_completed_sale is not None:
            raise ConflictError(
                detail="Este agendamento já possui uma venda concluída.",
                code="APPOINTMENT_ALREADY_BILLED",
            )

        if effective_client_id is None:
            effective_client_id = appt.client_id
        elif effective_client_id != appt.client_id:
            raise DomainValidationError(
                detail="O cliente informado difere do cliente vinculado ao agendamento.",
                code="APPOINTMENT_CLIENT_MISMATCH",
            )

        if effective_sale_prof_id is None:
            effective_sale_prof_id = appt.professional_id

        if appt.deposit_status == DepositStatus.PAID:
            deposit_deducted = money(appt.deposit_amount)

    # 2. Valida cliente (quando informado)
    client: Client | None = None
    if effective_client_id is not None:
        client_repo = ClientRepository(session, tenant.studio_id)
        client = await client_repo.get_by_id_or_404(
            effective_client_id, detail="Cliente não encontrado."
        )

    # 3. Ordena e trava todos os produtos (`PIERCING_PRODUCT`) com SELECT ... FOR UPDATE (anti-deadlock)
    qty_needed_by_product: dict[uuid.UUID, int] = defaultdict(int)
    for item_in in payload.items:
        if item_in.item_kind in {
            SaleItemKind.PIERCING_SERVICE,
            SaleItemKind.PIERCING_PRODUCT,
        }:
            if "piercing" not in tenant.enabled_modules:
                raise ForbiddenError(
                    detail="O módulo 'piercing' não está habilitado para este estúdio.",
                    code="MODULE_DISABLED",
                )
        elif item_in.item_kind == SaleItemKind.TATTOO_SESSION:
            if "tattoo" not in tenant.enabled_modules:
                raise ForbiddenError(
                    detail="O módulo 'tattoo' não está habilitado para este estúdio.",
                    code="MODULE_DISABLED",
                )

        if item_in.item_kind == SaleItemKind.PIERCING_PRODUCT:
            if item_in.product_id is None:
                raise DomainValidationError(
                    detail="Informe o product_id para itens do tipo PIERCING_PRODUCT.",
                    code="PRODUCT_ID_REQUIRED",
                )
            qty_needed_by_product[item_in.product_id] += item_in.quantity
        elif item_in.item_kind == SaleItemKind.PIERCING_SERVICE:
            if item_in.service_id is None:
                raise DomainValidationError(
                    detail="Informe o service_id para itens do tipo PIERCING_SERVICE.",
                    code="SERVICE_ID_REQUIRED",
                )

    locked_products: dict[uuid.UUID, PiercingProduct] = {}
    prod_repo = PiercingProductRepository(session, tenant.studio_id)
    for pid in sorted(qty_needed_by_product.keys(), key=str):
        prod = await prod_repo.get_by_id_for_update_or_404(pid)
        needed = qty_needed_by_product[pid]
        if prod.stock_quantity < needed:
            raise DomainValidationError(
                detail=(
                    f"Estoque insuficiente para '{prod.name}'. "
                    f"Disponível: {prod.stock_quantity}, solicitado: {needed}."
                ),
                code="INSUFFICIENT_STOCK",
            )
        locked_products[pid] = prod

    # 4. Carrega serviços e memberships de profissionais envolvidos
    svc_repo = PiercingServiceRepository(session, tenant.studio_id)
    membership_repo = StudioMembershipRepository(session, tenant.studio_id)
    memberships_cache: dict[uuid.UUID, StudioMembership] = {}

    async def _get_active_membership(prof_id: uuid.UUID) -> StudioMembership:
        if prof_id not in memberships_cache:
            m = await membership_repo.get_by_user_id(prof_id)
            if m is None or not m.is_active:
                raise DomainValidationError(
                    detail="O profissional informado em um dos itens não possui vínculo ativo neste estúdio.",
                    code="INVALID_PROFESSIONAL",
                )
            memberships_cache[prof_id] = m
        return memberships_cache[prof_id]

    if effective_sale_prof_id is not None:
        await _get_active_membership(effective_sale_prof_id)

    # 5. Prepara linhas brutas e descontos com precisão Decimal
    prepared_lines: list[dict[str, object]] = []
    subtotal_amount = ZERO
    sum_after_item_discounts = ZERO
    total_cost_snapshot = ZERO

    for item_in in payload.items:
        item_prof_id = item_in.professional_id or effective_sale_prof_id
        if item_prof_id is not None:
            await _get_active_membership(item_prof_id)

        if item_in.item_kind == SaleItemKind.PIERCING_PRODUCT:
            prod = locked_products[item_in.product_id]  # type: ignore[index]
            unit_price = (
                money(item_in.unit_price)
                if item_in.unit_price is not None
                else money(prod.sale_price)
            )
            unit_cost = money(prod.cost_price)
            desc = prod.name
        elif item_in.item_kind == SaleItemKind.PIERCING_SERVICE:
            svc: PiercingService = await svc_repo.get_by_id_or_404(
                item_in.service_id,  # type: ignore[arg-type]
                detail="Serviço de perfuração não encontrado.",
            )
            unit_price = (
                money(item_in.unit_price)
                if item_in.unit_price is not None
                else money(svc.base_price)
            )
            unit_cost = ZERO
            desc = svc.name
        else:
            if item_in.unit_price is None:
                raise DomainValidationError(
                    detail="Informe unit_price para sessão de tatuagem.",
                    code="UNIT_PRICE_REQUIRED",
                )
            unit_price = money(item_in.unit_price)
            unit_cost = ZERO
            desc = "Sessão de Tatuagem"

        line_gross = money(unit_price * item_in.quantity)
        item_disc = money(item_in.discount_amount)
        if item_disc > line_gross:
            raise DomainValidationError(
                detail=f"O desconto do item '{desc}' não pode superar seu valor bruto.",
                code="DISCOUNT_EXCEEDS_ITEM_TOTAL",
            )
        line_after_item_disc = money(line_gross - item_disc)
        line_cost_total = money(unit_cost * item_in.quantity)

        subtotal_amount = money(subtotal_amount + line_gross)
        sum_after_item_discounts = money(
            sum_after_item_discounts + line_after_item_disc
        )
        total_cost_snapshot = money(total_cost_snapshot + line_cost_total)

        prepared_lines.append(
            {
                "item_kind": item_in.item_kind,
                "service_id": item_in.service_id,
                "product_id": item_in.product_id,
                "professional_id": item_prof_id,
                "description_snapshot": desc,
                "quantity": item_in.quantity,
                "unit_price": unit_price,
                "unit_cost_snapshot": unit_cost,
                "line_gross": line_gross,
                "item_disc": item_disc,
                "line_after_item_disc": line_after_item_disc,
            }
        )

    checkout_discount = money(payload.discount_amount)
    if checkout_discount > sum_after_item_discounts:
        raise DomainValidationError(
            detail="O desconto geral da venda não pode superar o valor dos itens.",
            code="DISCOUNT_EXCEEDS_SUBTOTAL",
        )

    # Rateia eventual desconto geral proporcionalmente sobre os itens (ajustando centavo final)
    allocated_checkout_disc_sum = ZERO
    for idx, line in enumerate(prepared_lines):
        after_item_d = line["line_after_item_disc"]  # type: ignore[assignment]
        assert isinstance(after_item_d, Decimal)
        if checkout_discount == ZERO or sum_after_item_discounts == ZERO:
            extra_disc = ZERO
        elif idx == len(prepared_lines) - 1:
            extra_disc = money(checkout_discount - allocated_checkout_disc_sum)
        else:
            extra_disc = money(
                (checkout_discount * after_item_d) / sum_after_item_discounts
            )
            allocated_checkout_disc_sum = money(
                allocated_checkout_disc_sum + extra_disc
            )

        orig_item_disc = line["item_disc"]
        assert isinstance(orig_item_disc, Decimal)
        final_line_disc = money(orig_item_disc + extra_disc)
        line_gross = line["line_gross"]
        assert isinstance(line_gross, Decimal)
        line["final_discount"] = final_line_disc
        line["total_item_amount"] = money(line_gross - final_line_disc)

    total_discount_amount = money(
        sum((line["final_discount"] for line in prepared_lines), ZERO)  # type: ignore[arg-type]
    )
    effective_sale_revenue = money(subtotal_amount - total_discount_amount)

    if deposit_deducted > effective_sale_revenue:
        raise DomainValidationError(
            detail=(
                f"O sinal pago (R$ {deposit_deducted}) excede o total líquido da venda "
                f"(R$ {effective_sale_revenue})."
            ),
            code="DEPOSIT_EXCEEDS_SALE_TOTAL",
        )

    total_due_amount = money(effective_sale_revenue - deposit_deducted)
    payments_sum = money(
        sum((money(p.amount) for p in payload.payments), ZERO)
    )
    if payments_sum != total_due_amount:
        raise DomainValidationError(
            detail=(
                f"A soma dos pagamentos informados (R$ {payments_sum}) deve ser "
                f"exatamente igual ao restante a pagar (R$ {total_due_amount})."
            ),
            code="PAYMENT_TOTAL_MISMATCH",
        )

    # 6. Valida configurações de meios de pagamento
    pm_repo = PaymentMethodConfigRepository(session, tenant.studio_id)
    pm_map = {
        pm.method: pm for pm in await pm_repo.list_ordered() if pm.is_active
    }
    for p_in in payload.payments:
        if p_in.method not in pm_map:
            raise DomainValidationError(
                detail=f"O meio de pagamento '{p_in.method.value}' não está ativo neste estúdio.",
                code="PAYMENT_METHOD_INACTIVE",
            )

    # 7. Persiste Sale, SaleItems e Movimentos de Saída no Kardex (`OUT_SALE`)
    sale_repo = SaleRepository(session, tenant.studio_id)
    sale = await sale_repo.add(
        Sale(
            studio_id=tenant.studio_id,
            client_id=effective_client_id,
            appointment_id=appt.id if appt else None,
            professional_id=effective_sale_prof_id,
            status=SaleStatus.COMPLETED,
            competence_date=comp_date,
            subtotal_amount=subtotal_amount,
            discount_amount=total_discount_amount,
            deposit_deducted_amount=deposit_deducted,
            total_due_amount=total_due_amount,
            total_cost_snapshot=total_cost_snapshot,
            notes=payload.notes.strip() if payload.notes else None,
            created_by=tenant.user_id,
        )
    )

    sale_item_repo = SaleItemRepository(session, tenant.studio_id)
    mov_repo = InventoryMovementRepository(session, tenant.studio_id)
    saved_items: list[SaleItem] = []

    for line in prepared_lines:
        si = await sale_item_repo.add(
            SaleItem(
                studio_id=tenant.studio_id,
                sale_id=sale.id,
                item_kind=line["item_kind"],  # type: ignore[arg-type]
                service_id=line["service_id"],  # type: ignore[arg-type]
                product_id=line["product_id"],  # type: ignore[arg-type]
                professional_id=line["professional_id"],  # type: ignore[arg-type]
                description_snapshot=str(line["description_snapshot"]),
                quantity=int(line["quantity"]),  # type: ignore[arg-type]
                unit_price=line["unit_price"],  # type: ignore[arg-type]
                unit_cost_snapshot=line["unit_cost_snapshot"],  # type: ignore[arg-type]
                discount_amount=line["final_discount"],  # type: ignore[arg-type]
                total_item_amount=line["total_item_amount"],  # type: ignore[arg-type]
            )
        )
        saved_items.append(si)

        if si.item_kind == SaleItemKind.PIERCING_PRODUCT and si.product_id:
            prod = locked_products[si.product_id]
            new_stock = prod.stock_quantity - si.quantity
            prod.stock_quantity = new_stock
            prod.updated_by = tenant.user_id
            prod.updated_at = utcnow()

            await mov_repo.add(
                InventoryMovement(
                    studio_id=tenant.studio_id,
                    product_id=prod.id,
                    movement_type=InventoryMovementType.OUT_SALE,
                    quantity_delta=-si.quantity,
                    resulting_stock=new_stock,
                    unit_cost_snapshot=si.unit_cost_snapshot,
                    reference_sale_id=sale.id,
                    reason=f"Venda PDV #{str(sale.id)[:8]}",
                    created_by=tenant.user_id,
                )
            )

    # 8. Atualiza agendamento e procedimentos vinculados (se houver)
    pay_repo = PaymentRepository(session, tenant.studio_id)
    applied_deposit_fee = ZERO
    if appt is not None:
        appt_updates: dict[str, object] = {"updated_by": tenant.user_id}
        if appt.deposit_status == DepositStatus.PAID:
            appt_updates["deposit_status"] = DepositStatus.APPLIED_TO_SALE
            dep_pay = await pay_repo.get_deposit_payment_for_appointment(appt.id)
            if dep_pay is not None:
                applied_deposit_fee = money(dep_pay.fee_amount)

        if appt.status in {
            AppointmentStatus.AGENDADO,
            AppointmentStatus.CONFIRMADO,
            AppointmentStatus.EM_ATENDIMENTO,
        }:
            appt_updates["status"] = AppointmentStatus.CONCLUIDO

        appt_repo = AppointmentRepository(session, tenant.studio_id)
        await appt_repo.update_by_id(appt.id, appt_updates)

        # Vincula sale_id em procedimentos técnicos deste agendamento
        await session.execute(
            sa.update(PiercingProcedure)
            .where(
                PiercingProcedure.studio_id == tenant.studio_id,
                PiercingProcedure.appointment_id == appt.id,
                PiercingProcedure.sale_id.is_(None),
            )
            .values(sale_id=sale.id, updated_at=utcnow(), updated_by=tenant.user_id)
        )

    # 9. Registra pagamentos do checkout e lançamentos no Livro-Caixa (`SALE_PAYMENT`)
    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    checkout_fees_total = ZERO
    client_label = client.full_name if client else "Venda Balcão"

    for p_in in payload.payments:
        pm_cfg = pm_map[p_in.method]
        gross = money(p_in.amount)
        fee_amt, net_amt = compute_payment_fee_and_net(
            gross_amount=gross,
            fee_percentage=pm_cfg.fee_percentage,
            fixed_fee=pm_cfg.fixed_fee,
        )
        checkout_fees_total = money(checkout_fees_total + fee_amt)

        payment = await pay_repo.add(
            Payment(
                studio_id=tenant.studio_id,
                sale_id=sale.id,
                appointment_id=appt.id if appt else None,
                method=p_in.method,
                is_deposit=False,
                gross_amount=gross,
                fee_percentage_snapshot=pm_cfg.fee_percentage,
                fixed_fee_snapshot=pm_cfg.fixed_fee,
                fee_amount=fee_amt,
                net_amount=net_amt,
                paid_at=sold_at,
                created_by=tenant.user_id,
            )
        )
        await tx_repo.add(
            FinancialTransaction(
                studio_id=tenant.studio_id,
                type=FinancialTransactionType.INCOME,
                category=FinancialTransactionCategory.SALE_PAYMENT,
                cash_flow_direction=CashFlowDirection.INFLOW,
                payment_method=p_in.method,
                description=f"Recebimento venda PDV — {client_label}",
                gross_amount=gross,
                fee_amount=fee_amt,
                net_amount=net_amt,
                competence_date=comp_date,
                paid_at=sold_at,
                reference_sale_id=sale.id,
                reference_payment_id=payment.id,
                reference_appointment_id=appt.id if appt else None,
                created_by=tenant.user_id,
            )
        )

    # 10. Motor de Comissões por item
    total_sale_fees = money(checkout_fees_total + applied_deposit_fee)
    comm_repo = CommissionRepository(session, tenant.studio_id)

    for si in saved_items:
        if si.professional_id is None or si.total_item_amount <= ZERO:
            continue
        membership = memberships_cache[si.professional_id]
        pct = (
            membership.commission_service_pct
            if si.item_kind
            in {SaleItemKind.PIERCING_SERVICE, SaleItemKind.TATTOO_SESSION}
            else membership.commission_product_pct
        )
        if pct <= ZERO:
            continue

        if (
            tenant.commission_deducts_payment_fee
            and effective_sale_revenue > ZERO
            and total_sale_fees > ZERO
        ):
            allocated_fee = money(
                (total_sale_fees * si.total_item_amount) / effective_sale_revenue
            )
            base_amt = max(ZERO, money(si.total_item_amount - allocated_fee))
        else:
            base_amt = si.total_item_amount

        comm_amt = money((base_amt * pct) / HUNDRED)
        if comm_amt > ZERO:
            await comm_repo.add(
                Commission(
                    studio_id=tenant.studio_id,
                    professional_id=si.professional_id,
                    sale_id=sale.id,
                    sale_item_id=si.id,
                    item_kind=si.item_kind,
                    description=f"{si.description_snapshot} ({si.quantity}x)",
                    base_amount=base_amt,
                    commission_pct_snapshot=pct,
                    commission_amount=comm_amt,
                    status=CommissionStatus.PENDING,
                )
            )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="sales",
        entity_id=sale.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "subtotal_amount": str(subtotal_amount),
            "discount_amount": str(total_discount_amount),
            "deposit_deducted_amount": str(deposit_deducted),
            "total_due_amount": str(total_due_amount),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(sale)
    return (await serialize_sales_for_role(session, tenant, [sale]))[0]


async def list_sales(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    status: SaleStatus | None = None,
    client_id: uuid.UUID | None = None,
) -> list[SaleOwnerResponse | SaleStaffResponse]:
    repo = SaleRepository(session, tenant.studio_id)
    rows = list(
        await repo.list_filtered(
            date_from=date_from,
            date_to=date_to,
            status=status,
            client_id=client_id,
        )
    )
    return await serialize_sales_for_role(session, tenant, rows)


async def get_sale_detail(
    session: AsyncSession,
    tenant: TenantContext,
    sale_id: uuid.UUID,
) -> SaleOwnerResponse | SaleStaffResponse:
    repo = SaleRepository(session, tenant.studio_id)
    sale = await repo.get_by_id_or_404(sale_id, detail="Venda não encontrada.")
    return (await serialize_sales_for_role(session, tenant, [sale]))[0]


async def refund_sale(
    session: AsyncSession,
    tenant: TenantContext,
    sale_id: uuid.UUID,
    payload: SaleRefundRequest,
    *,
    request: Request | None = None,
) -> SaleOwnerResponse:
    sale_repo = SaleRepository(session, tenant.studio_id)
    sale = await sale_repo.get_by_id_for_update_or_404(sale_id)

    if sale.status == SaleStatus.REFUNDED:
        raise ConflictError(
            detail="Esta venda já foi estornada anteriormente.",
            code="SALE_ALREADY_REFUNDED",
        )

    now = utcnow()
    comp_date = timestamp_to_studio_date(now, tenant.timezone)
    reason_clean = payload.reason.strip()

    sale.status = SaleStatus.REFUNDED
    sale.refunded_at = now
    sale.refunded_by = tenant.user_id
    sale.refund_reason = reason_clean
    sale.updated_at = now

    # 1. Devolução de Estoque (`RETURN_REFUND`) com lock ordenado por product_id
    item_repo = SaleItemRepository(session, tenant.studio_id)
    sale_items = list(await item_repo.list_by_sale_ids([sale.id]))
    product_items = [
        it
        for it in sale_items
        if it.item_kind == SaleItemKind.PIERCING_PRODUCT and it.product_id is not None
    ]
    distinct_pids = sorted({it.product_id for it in product_items if it.product_id}, key=str)

    locked_products: dict[uuid.UUID, PiercingProduct] = {}
    for pid in distinct_pids:
        prod = (
            await session.execute(
                sa.select(PiercingProduct)
                .where(
                    PiercingProduct.studio_id == tenant.studio_id,
                    PiercingProduct.id == pid,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if prod is not None:
            locked_products[pid] = prod

    mov_repo = InventoryMovementRepository(session, tenant.studio_id)
    for it in product_items:
        if it.product_id and it.product_id in locked_products:
            prod = locked_products[it.product_id]
            new_stock = prod.stock_quantity + it.quantity
            prod.stock_quantity = new_stock
            prod.updated_by = tenant.user_id
            prod.updated_at = now
            await mov_repo.add(
                InventoryMovement(
                    studio_id=tenant.studio_id,
                    product_id=prod.id,
                    movement_type=InventoryMovementType.RETURN_REFUND,
                    quantity_delta=it.quantity,
                    resulting_stock=new_stock,
                    unit_cost_snapshot=it.unit_cost_snapshot,
                    reference_sale_id=sale.id,
                    reason=f"Estorno de venda: {reason_clean}",
                    created_by=tenant.user_id,
                )
            )

    # 2. Estorno Financeiro dos pagamentos do checkout
    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    sale_income_txs = (
        await session.execute(
            sa.select(FinancialTransaction).where(
                FinancialTransaction.studio_id == tenant.studio_id,
                FinancialTransaction.reference_sale_id == sale.id,
                FinancialTransaction.type == FinancialTransactionType.INCOME,
            )
        )
    ).scalars().all()

    for orig_tx in sale_income_txs:
        if not await tx_repo.has_reversal(orig_tx.id):
            await tx_repo.add(
                FinancialTransaction(
                    studio_id=tenant.studio_id,
                    type=FinancialTransactionType.REVERSAL,
                    category=FinancialTransactionCategory.REFUND_OUTFLOW,
                    cash_flow_direction=CashFlowDirection.OUTFLOW,
                    payment_method=orig_tx.payment_method,
                    description=f"Estorno venda PDV — {reason_clean}",
                    gross_amount=orig_tx.gross_amount,
                    fee_amount=ZERO,
                    net_amount=orig_tx.gross_amount,
                    competence_date=comp_date,
                    paid_at=now,
                    reference_sale_id=sale.id,
                    reversed_transaction_id=orig_tx.id,
                    created_by=tenant.user_id,
                )
            )

    # 3. Tratamento do Sinal de Agendamento vinculado (refund_deposit=True vs False/FORFEITED)
    if sale.appointment_id is not None and sale.deposit_deducted_amount > ZERO:
        appt = (
            await session.execute(
                sa.select(Appointment)
                .where(
                    Appointment.studio_id == tenant.studio_id,
                    Appointment.id == sale.appointment_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if appt is not None:
            if payload.refund_deposit:
                appt.deposit_status = DepositStatus.REFUNDED
                appt.updated_at = now
                appt.updated_by = tenant.user_id

                dep_tx = (
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

                rev_id = (
                    dep_tx.id
                    if dep_tx is not None and not await tx_repo.has_reversal(dep_tx.id)
                    else None
                )
                await tx_repo.add(
                    FinancialTransaction(
                        studio_id=tenant.studio_id,
                        type=FinancialTransactionType.REVERSAL,
                        category=FinancialTransactionCategory.REFUND_OUTFLOW,
                        cash_flow_direction=CashFlowDirection.OUTFLOW,
                        payment_method=appt.deposit_payment_method,
                        description=f"Estorno sinal de venda — {reason_clean}",
                        gross_amount=sale.deposit_deducted_amount,
                        fee_amount=ZERO,
                        net_amount=sale.deposit_deducted_amount,
                        competence_date=comp_date,
                        paid_at=now,
                        reference_sale_id=sale.id,
                        reference_appointment_id=appt.id,
                        reversed_transaction_id=rev_id,
                        created_by=tenant.user_id,
                    )
                )
            else:
                appt.deposit_status = DepositStatus.FORFEITED
                appt.updated_at = now
                appt.updated_by = tenant.user_id

    # 4. Reversão de Comissões (PENDING -> REVERSED; PAID -> mantém PAID + lançamento compensatório negativo)
    comm_repo = CommissionRepository(session, tenant.studio_id)
    sale_commissions = await comm_repo.list_by_sale_for_update(sale.id)

    for comm in sale_commissions:
        if comm.status == CommissionStatus.PENDING and comm.commission_amount > ZERO:
            comm.status = CommissionStatus.REVERSED
            comm.updated_at = now
        elif comm.status == CommissionStatus.PAID and comm.commission_amount > ZERO:
            await comm_repo.add(
                Commission(
                    studio_id=tenant.studio_id,
                    professional_id=comm.professional_id,
                    sale_id=sale.id,
                    sale_item_id=comm.sale_item_id,
                    item_kind=comm.item_kind,
                    description=f"Estorno compensatório: {comm.description}",
                    base_amount=money(-comm.base_amount),
                    commission_pct_snapshot=comm.commission_pct_snapshot,
                    commission_amount=money(-comm.commission_amount),
                    status=CommissionStatus.PENDING,
                )
            )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="sales",
        entity_id=sale.id,
        action=AuditAction.REFUND,
        metadata_diff={
            "reason": reason_clean,
            "refund_deposit": payload.refund_deposit,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(sale)

    res = (await serialize_sales_for_role(session, tenant, [sale]))[0]
    if not isinstance(res, SaleOwnerResponse):
        raise NotFoundError(detail="Erro ao serializar estorno.")
    return res
