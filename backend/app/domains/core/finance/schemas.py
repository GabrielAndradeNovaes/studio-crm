from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    CashFlowDirection,
    CommissionStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    PaymentMethodCode,
    SaleItemKind,
    SaleStatus,
)


def _ensure_tz_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("Data/hora deve incluir fuso horário explícito (ISO 8601).")
    return dt.astimezone(timezone.utc)


class SaleItemCheckoutInput(BaseModel):
    item_kind: SaleItemKind
    service_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    professional_id: uuid.UUID | None = None
    quantity: int = Field(default=1, gt=0, le=500)
    unit_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class SalePaymentCheckoutInput(BaseModel):
    method: PaymentMethodCode
    amount: Decimal = Field(..., gt=Decimal("0.00"))


class SaleCheckoutRequest(BaseModel):
    client_id: uuid.UUID | None = None
    appointment_id: uuid.UUID | None = None
    professional_id: uuid.UUID | None = None
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    items: list[SaleItemCheckoutInput] = Field(..., min_length=1)
    payments: list[SalePaymentCheckoutInput] = Field(default_factory=list)
    sold_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("sold_at")
    @classmethod
    def check_sold_tz(cls, v: datetime | None) -> datetime | None:
        return _ensure_tz_utc(v)


class SaleRefundRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=255)
    refund_deposit: bool = False


class SalePaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: PaymentMethodCode
    is_deposit: bool
    gross_amount: Decimal
    fee_percentage_snapshot: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    paid_at: datetime


class SaleItemStaffResponse(BaseModel):
    """DTO de item de venda para RECEPTION — omite `unit_cost_snapshot`."""

    id: uuid.UUID
    item_kind: SaleItemKind
    service_id: uuid.UUID | None
    product_id: uuid.UUID | None
    professional_id: uuid.UUID | None
    description_snapshot: str
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    total_item_amount: Decimal


class SaleItemOwnerResponse(SaleItemStaffResponse):
    """DTO exclusivo OWNER — inclui `unit_cost_snapshot`."""

    unit_cost_snapshot: Decimal


class SaleStaffResponse(BaseModel):
    """DTO de venda para RECEPTION — omite `total_cost_snapshot` e custos de itens."""

    id: uuid.UUID
    studio_id: uuid.UUID
    client_id: uuid.UUID | None
    client_name: str | None
    appointment_id: uuid.UUID | None
    professional_id: uuid.UUID | None
    professional_name: str | None
    status: SaleStatus
    competence_date: date
    subtotal_amount: Decimal
    discount_amount: Decimal
    deposit_deducted_amount: Decimal
    total_due_amount: Decimal
    notes: str | None
    refunded_at: datetime | None
    refund_reason: str | None
    created_at: datetime
    items: list[SaleItemStaffResponse]
    payments: list[SalePaymentResponse]


class SaleOwnerResponse(BaseModel):
    """DTO de venda exclusivo OWNER — inclui `total_cost_snapshot` e custos congelados."""

    id: uuid.UUID
    studio_id: uuid.UUID
    client_id: uuid.UUID | None
    client_name: str | None
    appointment_id: uuid.UUID | None
    professional_id: uuid.UUID | None
    professional_name: str | None
    status: SaleStatus
    competence_date: date
    subtotal_amount: Decimal
    discount_amount: Decimal
    deposit_deducted_amount: Decimal
    total_due_amount: Decimal
    total_cost_snapshot: Decimal
    notes: str | None
    refunded_at: datetime | None
    refund_reason: str | None
    created_at: datetime
    items: list[SaleItemOwnerResponse]
    payments: list[SalePaymentResponse]


class CommissionItemResponse(BaseModel):
    id: uuid.UUID
    studio_id: uuid.UUID
    professional_id: uuid.UUID
    professional_name: str
    sale_id: uuid.UUID
    sale_item_id: uuid.UUID | None
    item_kind: SaleItemKind
    description: str
    base_amount: Decimal
    commission_pct_snapshot: Decimal
    commission_amount: Decimal
    status: CommissionStatus
    paid_at: datetime | None
    payout_transaction_id: uuid.UUID | None
    created_at: datetime


class MyCommissionsSummaryResponse(BaseModel):
    pending_total: Decimal
    paid_total: Decimal
    reversed_total: Decimal
    items: list[CommissionItemResponse]


class CommissionPayoutRequest(BaseModel):
    professional_id: uuid.UUID
    commission_ids: list[uuid.UUID] = Field(..., min_length=1)
    payment_method: PaymentMethodCode = PaymentMethodCode.PIX
    notes: str | None = Field(default=None, max_length=255)


class CommissionPayoutResponse(BaseModel):
    payout_transaction_id: uuid.UUID
    professional_id: uuid.UUID
    total_paid_amount: Decimal
    paid_count: int
    paid_at: datetime


ManualCategoryAllowed = Literal[
    "FIXED_EXPENSE",
    "VARIABLE_EXPENSE",
    "INVENTORY_PURCHASE",
    "OTHER_INCOME",
]


class ManualTransactionCreateRequest(BaseModel):
    category: ManualCategoryAllowed
    description: str = Field(..., min_length=2, max_length=255)
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    payment_method: PaymentMethodCode | None = PaymentMethodCode.PIX
    competence_date: date | None = None
    paid_at: datetime | None = None

    @field_validator("paid_at")
    @classmethod
    def check_paid_tz(cls, v: datetime | None) -> datetime | None:
        return _ensure_tz_utc(v)


class ReverseTransactionRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=255)


class FinancialTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    type: FinancialTransactionType
    category: FinancialTransactionCategory
    cash_flow_direction: CashFlowDirection
    payment_method: PaymentMethodCode | None
    description: str
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    competence_date: date
    paid_at: datetime
    reference_sale_id: uuid.UUID | None
    reference_payment_id: uuid.UUID | None
    reference_appointment_id: uuid.UUID | None
    reversed_transaction_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime


class CashflowPeriodSummaryResponse(BaseModel):
    total_inflows: Decimal
    total_outflows: Decimal
    net_balance: Decimal
    transactions: list[FinancialTransactionResponse]


class PaymentMethodBreakdownItem(BaseModel):
    method: PaymentMethodCode
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    count: int


class DailyRegisterResponse(BaseModel):
    """
    Caixa Operacional do Dia (OWNER e RECEPTION).
    Omite estritamente qualquer campo de CMV, custo, despesa do estúdio ou lucro líquido.
    """

    date: date
    timezone: str
    completed_sales_count: int
    deposits_received_count: int
    sales_checkout_gross: Decimal
    deposits_received_gross: Decimal
    refunds_outflow_total: Decimal
    net_operational_cash: Decimal
    by_payment_method: list[PaymentMethodBreakdownItem]
    sales: list[SaleStaffResponse]


class ProfessionalPerformanceItem(BaseModel):
    professional_id: uuid.UUID
    professional_name: str
    items_count: int
    gross_revenue_generated: Decimal
    commissions_generated: Decimal


class ExecutiveDashboardResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    gross_revenue: Decimal
    cash_inflow_net: Decimal
    payment_fees_total: Decimal
    jewelry_cogs_total: Decimal
    commissions_generated_total: Decimal
    commissions_pending_total: Decimal
    operating_expenses_total: Decimal
    estimated_net_profit: Decimal
    completed_sales_count: int
    average_ticket: Decimal
    by_payment_method: list[PaymentMethodBreakdownItem]
    by_professional: list[ProfessionalPerformanceItem]
