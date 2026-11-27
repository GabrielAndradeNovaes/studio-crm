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
    AuditAction,
    CashFlowDirection,
    CommissionStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    PaymentMethodCode,
    SaleStatus,
    StudioRole,
)
from app.core.exceptions import ConflictError, DomainValidationError
from app.core.rbac import TenantContext
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import (
    timestamp_to_studio_date,
    today_in_studio_timezone,
    utcnow,
)
from app.domains.core.finance.models import (
    Commission,
    FinancialTransaction,
    Payment,
    Sale,
    SaleItem,
)
from app.domains.core.finance.money import ZERO, money
from app.domains.core.finance.pos_service import serialize_sales_for_role
from app.domains.core.finance.repository import (
    CommissionRepository,
    FinancialTransactionRepository,
    SaleRepository,
)
from app.domains.core.finance.schemas import (
    CashflowPeriodSummaryResponse,
    CommissionItemResponse,
    CommissionPayoutRequest,
    CommissionPayoutResponse,
    DailyRegisterResponse,
    ExecutiveDashboardResponse,
    FinancialTransactionResponse,
    ManualTransactionCreateRequest,
    MyCommissionsSummaryResponse,
    PaymentMethodBreakdownItem,
    ProfessionalPerformanceItem,
    ReverseTransactionRequest,
    SaleStaffResponse,
)
from app.domains.core.users.models import User


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _enrich_commissions(
    session: AsyncSession, rows: list[Commission]
) -> list[CommissionItemResponse]:
    if not rows:
        return []
    prof_ids = {r.professional_id for r in rows}
    with bypass_tenant_filter():
        users = (
            await session.execute(sa.select(User).where(User.id.in_(prof_ids)))
        ).scalars().all()
    users_map = {u.id: u.name for u in users}

    return [
        CommissionItemResponse(
            id=c.id,
            studio_id=c.studio_id,
            professional_id=c.professional_id,
            professional_name=users_map.get(c.professional_id, "Profissional"),
            sale_id=c.sale_id,
            sale_item_id=c.sale_item_id,
            item_kind=c.item_kind,
            description=c.description,
            base_amount=c.base_amount,
            commission_pct_snapshot=c.commission_pct_snapshot,
            commission_amount=c.commission_amount,
            status=c.status,
            paid_at=_ensure_utc(c.paid_at) if c.paid_at else None,
            payout_transaction_id=c.payout_transaction_id,
            created_at=_ensure_utc(c.created_at),
        )
        for c in rows
    ]


async def list_commissions_for_owner(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    professional_id: uuid.UUID | None = None,
    status: CommissionStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CommissionItemResponse]:
    sale_ids: list[uuid.UUID] | None = None
    if date_from is not None or date_to is not None:
        sale_stmt = sa.select(Sale.id).where(Sale.studio_id == tenant.studio_id)
        if date_from is not None:
            sale_stmt = sale_stmt.where(Sale.competence_date >= date_from)
        if date_to is not None:
            sale_stmt = sale_stmt.where(Sale.competence_date <= date_to)
        sale_ids = list((await session.execute(sale_stmt)).scalars().all())

    comm_repo = CommissionRepository(session, tenant.studio_id)
    rows = list(
        await comm_repo.list_filtered(
            professional_id=professional_id,
            status=status,
            sale_ids=sale_ids,
        )
    )
    return await _enrich_commissions(session, rows)


async def get_my_commissions_summary(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> MyCommissionsSummaryResponse:
    items = await list_commissions_for_owner(
        session,
        tenant,
        professional_id=tenant.user_id,
        date_from=date_from,
        date_to=date_to,
    )
    pending_total = money(
        sum(
            (it.commission_amount for it in items if it.status == CommissionStatus.PENDING),
            ZERO,
        )
    )
    paid_total = money(
        sum(
            (it.commission_amount for it in items if it.status == CommissionStatus.PAID),
            ZERO,
        )
    )
    reversed_total = money(
        sum(
            (
                it.commission_amount
                for it in items
                if it.status == CommissionStatus.REVERSED
            ),
            ZERO,
        )
    )
    return MyCommissionsSummaryResponse(
        pending_total=pending_total,
        paid_total=paid_total,
        reversed_total=reversed_total,
        items=items,
    )


async def payout_professional_commissions(
    session: AsyncSession,
    tenant: TenantContext,
    payload: CommissionPayoutRequest,
    *,
    request: Request | None = None,
) -> CommissionPayoutResponse:
    unique_ids = list(dict.fromkeys(payload.commission_ids))
    comm_repo = CommissionRepository(session, tenant.studio_id)
    locked_comms = list(await comm_repo.list_by_ids_for_update(unique_ids))

    if len(locked_comms) != len(unique_ids):
        raise DomainValidationError(
            detail="Uma ou mais comissões informadas não foram encontradas neste estúdio.",
            code="COMMISSION_NOT_FOUND",
        )

    for c in locked_comms:
        if c.professional_id != payload.professional_id:
            raise DomainValidationError(
                detail="Todas as comissões do lote devem pertencer ao mesmo profissional.",
                code="COMMISSION_PROFESSIONAL_MISMATCH",
            )
        if c.status != CommissionStatus.PENDING:
            raise ConflictError(
                detail="Apenas comissões com status PENDING podem ser incluídas no repasse.",
                code="COMMISSION_NOT_PENDING",
            )

    total_payout = money(sum((c.commission_amount for c in locked_comms), ZERO))
    if total_payout <= ZERO:
        raise DomainValidationError(
            detail=f"O valor líquido do repasse deve ser maior que zero (calculado: R$ {total_payout}).",
            code="PAYOUT_TOTAL_MUST_BE_POSITIVE",
        )

    with bypass_tenant_filter():
        prof_user = (
            await session.execute(
                sa.select(User).where(User.id == payload.professional_id)
            )
        ).scalar_one_or_none()
    prof_name = prof_user.name if prof_user else "Profissional"

    now = utcnow()
    comp_date = timestamp_to_studio_date(now, tenant.timezone)
    desc = f"Repasse de comissões ({len(locked_comms)} itens) — {prof_name}"
    if payload.notes and payload.notes.strip():
        desc = f"{desc} | {payload.notes.strip()}"

    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    payout_tx = await tx_repo.add(
        FinancialTransaction(
            studio_id=tenant.studio_id,
            type=FinancialTransactionType.EXPENSE,
            category=FinancialTransactionCategory.COMMISSION_PAYOUT,
            cash_flow_direction=CashFlowDirection.OUTFLOW,
            payment_method=payload.payment_method,
            description=desc[:255],
            gross_amount=total_payout,
            fee_amount=ZERO,
            net_amount=total_payout,
            competence_date=comp_date,
            paid_at=now,
            created_by=tenant.user_id,
        )
    )

    for c in locked_comms:
        c.status = CommissionStatus.PAID
        c.paid_at = now
        c.payout_transaction_id = payout_tx.id
        c.updated_at = now

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="commissions",
        entity_id=payout_tx.id,
        action=AuditAction.COMMISSION_PAYOUT,
        metadata_diff={
            "professional_id": str(payload.professional_id),
            "paid_count": len(locked_comms),
            "total_paid_amount": str(total_payout),
        },
        request=request,
    )
    await session.commit()

    return CommissionPayoutResponse(
        payout_transaction_id=payout_tx.id,
        professional_id=payload.professional_id,
        total_paid_amount=total_payout,
        paid_count=len(locked_comms),
        paid_at=now,
    )


async def list_financial_transactions(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    tx_type: FinancialTransactionType | None = None,
    category: FinancialTransactionCategory | None = None,
    offset: int = 0,
    limit: int = 200,
) -> CashflowPeriodSummaryResponse:
    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    rows = list(
        await tx_repo.list_filtered(
            date_from=date_from,
            date_to=date_to,
            tx_type=tx_type,
            category=category,
            offset=offset,
            limit=limit,
        )
    )

    # Calcula totais de todo o período filtrado (sem paginação curta)
    sum_stmt = sa.select(
        FinancialTransaction.cash_flow_direction,
        sa.func.coalesce(sa.func.sum(FinancialTransaction.net_amount), 0),
    ).where(FinancialTransaction.studio_id == tenant.studio_id)
    if date_from is not None:
        sum_stmt = sum_stmt.where(FinancialTransaction.competence_date >= date_from)
    if date_to is not None:
        sum_stmt = sum_stmt.where(FinancialTransaction.competence_date <= date_to)
    if tx_type is not None:
        sum_stmt = sum_stmt.where(FinancialTransaction.type == tx_type)
    if category is not None:
        sum_stmt = sum_stmt.where(FinancialTransaction.category == category)
    sum_stmt = sum_stmt.group_by(FinancialTransaction.cash_flow_direction)

    agg_rows = (await session.execute(sum_stmt)).all()
    total_inflows = ZERO
    total_outflows = ZERO
    for direction, total_val in agg_rows:
        if direction == CashFlowDirection.INFLOW:
            total_inflows = money(total_val)
        elif direction == CashFlowDirection.OUTFLOW:
            total_outflows = money(total_val)

    return CashflowPeriodSummaryResponse(
        total_inflows=total_inflows,
        total_outflows=total_outflows,
        net_balance=money(total_inflows - total_outflows),
        transactions=[FinancialTransactionResponse.model_validate(r) for r in rows],
    )


async def create_manual_financial_transaction(
    session: AsyncSession,
    tenant: TenantContext,
    payload: ManualTransactionCreateRequest,
    *,
    request: Request | None = None,
) -> FinancialTransactionResponse:
    cat = FinancialTransactionCategory(payload.category)
    is_income = cat == FinancialTransactionCategory.OTHER_INCOME
    tx_type = (
        FinancialTransactionType.INCOME
        if is_income
        else FinancialTransactionType.EXPENSE
    )
    direction = CashFlowDirection.INFLOW if is_income else CashFlowDirection.OUTFLOW

    paid_at = payload.paid_at or utcnow()
    comp_date = payload.competence_date or timestamp_to_studio_date(
        paid_at, tenant.timezone
    )
    amt = money(payload.amount)

    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    tx = await tx_repo.add(
        FinancialTransaction(
            studio_id=tenant.studio_id,
            type=tx_type,
            category=cat,
            cash_flow_direction=direction,
            payment_method=payload.payment_method,
            description=payload.description.strip(),
            gross_amount=amt,
            fee_amount=ZERO,
            net_amount=amt,
            competence_date=comp_date,
            paid_at=paid_at,
            created_by=tenant.user_id,
        )
    )
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="financial_transactions",
        entity_id=tx.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "type": tx.type.value,
            "category": tx.category.value,
            "amount": str(amt),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(tx)
    return FinancialTransactionResponse.model_validate(tx)


async def reverse_financial_transaction(
    session: AsyncSession,
    tenant: TenantContext,
    tx_id: uuid.UUID,
    payload: ReverseTransactionRequest,
    *,
    request: Request | None = None,
) -> FinancialTransactionResponse:
    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    orig = await tx_repo.get_by_id_for_update_or_404(tx_id)

    if orig.type == FinancialTransactionType.REVERSAL:
        raise DomainValidationError(
            detail="Não é permitido estornar um lançamento que já é um estorno.",
            code="CANNOT_REVERSE_REVERSAL",
        )
    if await tx_repo.has_reversal(orig.id):
        raise ConflictError(
            detail="Este lançamento financeiro já foi estornado anteriormente.",
            code="TRANSACTION_ALREADY_REVERSED",
        )
    if orig.reference_sale_id is not None:
        raise DomainValidationError(
            detail="Pagamentos de venda devem ser estornados pelo endpoint de estorno de venda (/sales/{id}/refund).",
            code="USE_SALE_REFUND_ENDPOINT",
        )

    now = utcnow()
    comp_date = timestamp_to_studio_date(now, tenant.timezone)
    opposite_dir = (
        CashFlowDirection.OUTFLOW
        if orig.cash_flow_direction == CashFlowDirection.INFLOW
        else CashFlowDirection.INFLOW
    )
    rev_category = (
        FinancialTransactionCategory.REFUND_OUTFLOW
        if opposite_dir == CashFlowDirection.OUTFLOW
        else orig.category
    )

    reversal = await tx_repo.add(
        FinancialTransaction(
            studio_id=tenant.studio_id,
            type=FinancialTransactionType.REVERSAL,
            category=rev_category,
            cash_flow_direction=opposite_dir,
            payment_method=orig.payment_method,
            description=f"Estorno: {orig.description[:140]} — {payload.reason.strip()}"[:255],
            gross_amount=orig.gross_amount,
            fee_amount=ZERO,
            net_amount=orig.net_amount,
            competence_date=comp_date,
            paid_at=now,
            reversed_transaction_id=orig.id,
            created_by=tenant.user_id,
        )
    )
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="financial_transactions",
        entity_id=reversal.id,
        action=AuditAction.REFUND,
        metadata_diff={
            "reversed_transaction_id": str(orig.id),
            "reason": payload.reason.strip(),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(reversal)
    return FinancialTransactionResponse.model_validate(reversal)


async def get_daily_operational_register(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    target_date: date | None = None,
) -> DailyRegisterResponse:
    today_local = today_in_studio_timezone(tenant.timezone)
    effective_date = (
        target_date
        if (target_date is not None and tenant.role == StudioRole.OWNER)
        else today_local
    )

    sale_repo = SaleRepository(session, tenant.studio_id)
    day_sales = list(
        await sale_repo.list_filtered(
            date_from=effective_date,
            date_to=effective_date,
        )
    )
    staff_sales = [
        SaleStaffResponse.model_validate(s)
        for s in await serialize_sales_for_role(
            session, tenant, day_sales, force_staff_view=True
        )
    ]

    tx_repo = FinancialTransactionRepository(session, tenant.studio_id)
    day_txs = list(
        await tx_repo.list_filtered(
            date_from=effective_date,
            date_to=effective_date,
            limit=500,
        )
    )

    sales_checkout_gross = ZERO
    deposits_received_gross = ZERO
    deposits_received_count = 0
    refunds_outflow_total = ZERO
    net_operational_cash = ZERO

    by_pm: dict[PaymentMethodCode, dict[str, Decimal | int]] = defaultdict(
        lambda: {"gross": ZERO, "fee": ZERO, "net": ZERO, "count": 0}
    )

    for tx in day_txs:
        if tx.category == FinancialTransactionCategory.SALE_PAYMENT:
            sales_checkout_gross = money(sales_checkout_gross + tx.gross_amount)
            net_operational_cash = money(net_operational_cash + tx.net_amount)
            if tx.payment_method:
                b = by_pm[tx.payment_method]
                b["gross"] = money(Decimal(b["gross"]) + tx.gross_amount)
                b["fee"] = money(Decimal(b["fee"]) + tx.fee_amount)
                b["net"] = money(Decimal(b["net"]) + tx.net_amount)
                b["count"] = int(b["count"]) + 1
        elif tx.category == FinancialTransactionCategory.APPOINTMENT_DEPOSIT:
            deposits_received_gross = money(deposits_received_gross + tx.gross_amount)
            deposits_received_count += 1
            net_operational_cash = money(net_operational_cash + tx.net_amount)
            if tx.payment_method:
                b = by_pm[tx.payment_method]
                b["gross"] = money(Decimal(b["gross"]) + tx.gross_amount)
                b["fee"] = money(Decimal(b["fee"]) + tx.fee_amount)
                b["net"] = money(Decimal(b["net"]) + tx.net_amount)
                b["count"] = int(b["count"]) + 1
        elif tx.category == FinancialTransactionCategory.REFUND_OUTFLOW:
            refunds_outflow_total = money(refunds_outflow_total + tx.net_amount)
            net_operational_cash = money(net_operational_cash - tx.net_amount)

    completed_count = sum(1 for s in day_sales if s.status == SaleStatus.COMPLETED)

    pm_breakdown = [
        PaymentMethodBreakdownItem(
            method=m,
            gross_amount=Decimal(vals["gross"]),
            fee_amount=Decimal(vals["fee"]),
            net_amount=Decimal(vals["net"]),
            count=int(vals["count"]),
        )
        for m, vals in sorted(by_pm.items(), key=lambda kv: kv[0].value)
    ]

    return DailyRegisterResponse(
        date=effective_date,
        timezone=tenant.timezone,
        completed_sales_count=completed_count,
        deposits_received_count=deposits_received_count,
        sales_checkout_gross=sales_checkout_gross,
        deposits_received_gross=deposits_received_gross,
        refunds_outflow_total=refunds_outflow_total,
        net_operational_cash=net_operational_cash,
        by_payment_method=pm_breakdown,
        sales=staff_sales,
    )


async def get_executive_dashboard(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ExecutiveDashboardResponse:
    today_local = today_in_studio_timezone(tenant.timezone)
    effective_to = date_to or today_local
    effective_from = date_from or effective_to.replace(day=1)
    if effective_to < effective_from:
        raise DomainValidationError(
            detail="A data final deve ser igual ou posterior à data inicial.",
            code="INVALID_DATE_RANGE",
        )

    # 1. Vendas concluídas no período (Competência)
    completed_sales = (
        await session.execute(
            sa.select(Sale).where(
                Sale.studio_id == tenant.studio_id,
                Sale.status == SaleStatus.COMPLETED,
                Sale.competence_date >= effective_from,
                Sale.competence_date <= effective_to,
            )
        )
    ).scalars().all()

    completed_sales_count = len(completed_sales)
    completed_sale_ids = [s.id for s in completed_sales]
    applied_appt_ids = [
        s.appointment_id
        for s in completed_sales
        if s.appointment_id is not None and s.deposit_deducted_amount > ZERO
    ]

    gross_revenue = money(
        sum(
            (money(s.subtotal_amount - s.discount_amount) for s in completed_sales),
            ZERO,
        )
    )
    jewelry_cogs_total = money(
        sum((money(s.total_cost_snapshot) for s in completed_sales), ZERO)
    )
    average_ticket = (
        money(gross_revenue / completed_sales_count)
        if completed_sales_count > 0
        else ZERO
    )

    # 2. Taxas de pagamento das vendas concluídas (checkout + sinais aplicados) & quebra por meio
    relevant_payments: list[Payment] = []
    if completed_sale_ids:
        checkout_pays = (
            await session.execute(
                sa.select(Payment).where(
                    Payment.studio_id == tenant.studio_id,
                    Payment.sale_id.in_(completed_sale_ids),
                )
            )
        ).scalars().all()
        relevant_payments.extend(checkout_pays)

    if applied_appt_ids:
        dep_pays = (
            await session.execute(
                sa.select(Payment).where(
                    Payment.studio_id == tenant.studio_id,
                    Payment.appointment_id.in_(applied_appt_ids),
                    Payment.is_deposit.is_(True),
                )
            )
        ).scalars().all()
        relevant_payments.extend(dep_pays)

    payment_fees_total = money(
        sum((money(p.fee_amount) for p in relevant_payments), ZERO)
    )

    by_pm: dict[PaymentMethodCode, dict[str, Decimal | int]] = defaultdict(
        lambda: {"gross": ZERO, "fee": ZERO, "net": ZERO, "count": 0}
    )
    for p in relevant_payments:
        b = by_pm[p.method]
        b["gross"] = money(Decimal(b["gross"]) + p.gross_amount)
        b["fee"] = money(Decimal(p.fee_amount) + Decimal(b["fee"]))
        b["net"] = money(Decimal(b["net"]) + p.net_amount)
        b["count"] = int(b["count"]) + 1

    pm_breakdown = [
        PaymentMethodBreakdownItem(
            method=m,
            gross_amount=Decimal(vals["gross"]),
            fee_amount=Decimal(vals["fee"]),
            net_amount=Decimal(vals["net"]),
            count=int(vals["count"]),
        )
        for m, vals in sorted(by_pm.items(), key=lambda kv: kv[0].value)
    ]

    # 3. Comissões geradas pelas vendas concluídas & saldo pendente global
    commissions_generated_total = ZERO
    comm_by_prof: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)

    if completed_sale_ids:
        period_comms = (
            await session.execute(
                sa.select(Commission).where(
                    Commission.studio_id == tenant.studio_id,
                    Commission.sale_id.in_(completed_sale_ids),
                    Commission.status != CommissionStatus.REVERSED,
                    Commission.commission_amount > ZERO,
                )
            )
        ).scalars().all()
        for c in period_comms:
            commissions_generated_total = money(
                commissions_generated_total + c.commission_amount
            )
            comm_by_prof[c.professional_id] = money(
                comm_by_prof[c.professional_id] + c.commission_amount
            )

    pending_sum_val = (
        await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(Commission.commission_amount), 0)
            ).where(
                Commission.studio_id == tenant.studio_id,
                Commission.status == CommissionStatus.PENDING,
            )
        )
    ).scalar_one()
    commissions_pending_total = money(pending_sum_val)

    # 4. Fluxo de Caixa Líquido de Entradas & Despesas Operacionais do Período
    period_txs = (
        await session.execute(
            sa.select(FinancialTransaction).where(
                FinancialTransaction.studio_id == tenant.studio_id,
                FinancialTransaction.competence_date >= effective_from,
                FinancialTransaction.competence_date <= effective_to,
            )
        )
    ).scalars().all()

    cash_inflow_net = ZERO
    operating_expenses_total = ZERO
    expense_cats = {
        FinancialTransactionCategory.FIXED_EXPENSE,
        FinancialTransactionCategory.VARIABLE_EXPENSE,
        FinancialTransactionCategory.INVENTORY_PURCHASE,
    }

    for tx in period_txs:
        if tx.type == FinancialTransactionType.INCOME and tx.category in {
            FinancialTransactionCategory.SALE_PAYMENT,
            FinancialTransactionCategory.APPOINTMENT_DEPOSIT,
            FinancialTransactionCategory.OTHER_INCOME,
        }:
            cash_inflow_net = money(cash_inflow_net + tx.net_amount)
        elif tx.category == FinancialTransactionCategory.REFUND_OUTFLOW:
            cash_inflow_net = money(cash_inflow_net - tx.net_amount)
        elif tx.type == FinancialTransactionType.EXPENSE and tx.category in expense_cats:
            operating_expenses_total = money(
                operating_expenses_total + tx.net_amount
            )
        elif (
            tx.type == FinancialTransactionType.REVERSAL
            and tx.cash_flow_direction == CashFlowDirection.INFLOW
            and tx.category in expense_cats
        ):
            operating_expenses_total = max(
                ZERO, money(operating_expenses_total - tx.net_amount)
            )

    estimated_net_profit = money(
        gross_revenue
        - payment_fees_total
        - jewelry_cogs_total
        - commissions_generated_total
        - operating_expenses_total
    )

    # 5. Ranking por Profissional
    by_prof_items: dict[uuid.UUID, dict[str, Decimal | int]] = defaultdict(
        lambda: {"count": 0, "revenue": ZERO}
    )
    if completed_sale_ids:
        s_items = (
            await session.execute(
                sa.select(SaleItem).where(
                    SaleItem.studio_id == tenant.studio_id,
                    SaleItem.sale_id.in_(completed_sale_ids),
                    SaleItem.professional_id.is_not(None),
                )
            )
        ).scalars().all()
        for it in s_items:
            if it.professional_id:
                bp = by_prof_items[it.professional_id]
                bp["count"] = int(bp["count"]) + it.quantity
                bp["revenue"] = money(Decimal(bp["revenue"]) + it.total_item_amount)

    prof_ids = set(by_prof_items.keys()) | set(comm_by_prof.keys())
    users_map: dict[uuid.UUID, str] = {}
    if prof_ids:
        with bypass_tenant_filter():
            u_rows = (
                await session.execute(sa.select(User).where(User.id.in_(prof_ids)))
            ).scalars().all()
        users_map = {u.id: u.name for u in u_rows}

    prof_ranking = [
        ProfessionalPerformanceItem(
            professional_id=pid,
            professional_name=users_map.get(pid, "Profissional"),
            items_count=int(by_prof_items[pid]["count"]),
            gross_revenue_generated=Decimal(by_prof_items[pid]["revenue"]),
            commissions_generated=comm_by_prof[pid],
        )
        for pid in prof_ids
    ]
    prof_ranking.sort(key=lambda x: x.gross_revenue_generated, reverse=True)

    return ExecutiveDashboardResponse(
        date_from=effective_from,
        date_to=effective_to,
        timezone=tenant.timezone,
        gross_revenue=gross_revenue,
        cash_inflow_net=cash_inflow_net,
        payment_fees_total=payment_fees_total,
        jewelry_cogs_total=jewelry_cogs_total,
        commissions_generated_total=commissions_generated_total,
        commissions_pending_total=commissions_pending_total,
        operating_expenses_total=operating_expenses_total,
        estimated_net_profit=estimated_net_profit,
        completed_sales_count=completed_sales_count,
        average_ticket=average_ticket,
        by_payment_method=pm_breakdown,
        by_professional=prof_ranking,
    )
