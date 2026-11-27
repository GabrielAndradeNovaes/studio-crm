from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import (
    CashFlowDirection,
    CommissionStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    PaymentMethodCode,
    SaleItemKind,
    SaleStatus,
)
from app.core.timezone import utcnow


class Sale(UUIDPrimaryKeyMixin, TenantModelMixin, TimestampMixin, Base):
    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_studio_comp_status", "studio_id", "competence_date", "status"),
        Index("ix_sales_studio_appt", "studio_id", "appointment_id"),
        CheckConstraint("subtotal_amount >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount_amount >= 0", name="discount_non_negative"),
        CheckConstraint("deposit_deducted_amount >= 0", name="deposit_deducted_non_negative"),
        CheckConstraint("total_due_amount >= 0", name="total_due_non_negative"),
        CheckConstraint("total_cost_snapshot >= 0", name="total_cost_non_negative"),
    )

    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, name="sale_status_enum", native_enum=False),
        default=SaleStatus.COMPLETED,
        nullable=False,
    )
    competence_date: Mapped[date] = mapped_column(Date, nullable=False)

    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    deposit_deducted_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    total_due_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    refund_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SaleItem(UUIDPrimaryKeyMixin, TenantModelMixin, Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        Index("ix_sale_items_studio_sale", "studio_id", "sale_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("unit_cost_snapshot >= 0", name="unit_cost_non_negative"),
        CheckConstraint("discount_amount >= 0", name="item_discount_non_negative"),
        CheckConstraint("total_item_amount >= 0", name="total_item_non_negative"),
    )

    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_kind: Mapped[SaleItemKind] = mapped_column(
        Enum(SaleItemKind, name="sale_item_kind_enum", native_enum=False),
        nullable=False,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_services.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    total_item_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Payment(UUIDPrimaryKeyMixin, TenantModelMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_studio_sale", "studio_id", "sale_id"),
        Index("ix_payments_studio_appt", "studio_id", "appointment_id"),
        CheckConstraint("gross_amount > 0", name="payment_gross_positive"),
        CheckConstraint("fee_amount >= 0", name="payment_fee_non_negative"),
    )

    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    method: Mapped[PaymentMethodCode] = mapped_column(
        Enum(PaymentMethodCode, name="payment_method_enum", native_enum=False),
        nullable=False,
    )
    is_deposit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_percentage_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )
    fixed_fee_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class FinancialTransaction(UUIDPrimaryKeyMixin, TenantModelMixin, Base):
    """
    Livro-caixa imutável (append-only).
    Proibida exclusão física; correções ou estornos geram novo registro `REVERSAL`.
    """

    __tablename__ = "financial_transactions"
    __table_args__ = (
        Index(
            "ix_fin_tx_studio_comp_type",
            "studio_id",
            "competence_date",
            "type",
            "category",
        ),
        CheckConstraint("gross_amount > 0", name="fin_tx_gross_positive"),
        CheckConstraint("fee_amount >= 0", name="fin_tx_fee_non_negative"),
    )

    type: Mapped[FinancialTransactionType] = mapped_column(
        Enum(FinancialTransactionType, name="fin_tx_type_enum", native_enum=False),
        nullable=False,
    )
    category: Mapped[FinancialTransactionCategory] = mapped_column(
        Enum(
            FinancialTransactionCategory,
            name="fin_tx_category_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    cash_flow_direction: Mapped[CashFlowDirection] = mapped_column(
        Enum(CashFlowDirection, name="cash_flow_dir_enum", native_enum=False),
        nullable=False,
    )
    payment_method: Mapped[PaymentMethodCode | None] = mapped_column(
        Enum(PaymentMethodCode, name="fin_tx_pm_enum", native_enum=False),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    competence_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    reference_sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sales.id", ondelete="SET NULL"),
        nullable=True,
    )
    reference_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    reference_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    reversed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Commission(UUIDPrimaryKeyMixin, TenantModelMixin, TimestampMixin, Base):
    """
    Registro de comissão por item atendido/vendido.
    `commission_amount` pode ser negativo em lançamentos compensatórios de vendas
    estornadas cujas comissões originais já haviam sido pagas (`PAID`).
    """

    __tablename__ = "commissions"
    __table_args__ = (
        Index(
            "ix_commissions_studio_prof_status",
            "studio_id",
            "professional_id",
            "status",
        ),
        Index("ix_commissions_studio_sale", "studio_id", "sale_id"),
    )

    professional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sale_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_kind: Mapped[SaleItemKind] = mapped_column(
        Enum(SaleItemKind, name="commission_item_kind_enum", native_enum=False),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)

    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission_pct_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[CommissionStatus] = mapped_column(
        Enum(CommissionStatus, name="commission_status_enum", native_enum=False),
        default=CommissionStatus.PENDING,
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payout_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
