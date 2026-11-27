"""Phase 4: POS sales, sale_items, payments, financial_transactions, and commissions

Revision ID: 20261127_0004
Revises: 20261126_0003
Create Date: 2026-11-27 09:35:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261127_0004"
down_revision: Union[str, None] = "20261126_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("professional_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("competence_date", sa.Date(), nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "deposit_deducted_amount", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("total_due_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "total_cost_snapshot", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_by", sa.Uuid(), nullable=True),
        sa.Column("refund_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "subtotal_amount >= 0", name=op.f("ck_sales_subtotal_non_negative")
        ),
        sa.CheckConstraint(
            "discount_amount >= 0", name=op.f("ck_sales_discount_non_negative")
        ),
        sa.CheckConstraint(
            "deposit_deducted_amount >= 0",
            name=op.f("ck_sales_deposit_deducted_non_negative"),
        ),
        sa.CheckConstraint(
            "total_due_amount >= 0", name=op.f("ck_sales_total_due_non_negative")
        ),
        sa.CheckConstraint(
            "total_cost_snapshot >= 0", name=op.f("ck_sales_total_cost_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_sales_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_sales_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_sales_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["users.id"],
            name=op.f("fk_sales_professional_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_sales_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["refunded_by"],
            ["users.id"],
            name=op.f("fk_sales_refunded_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales")),
    )
    op.create_index(op.f("ix_sales_studio_id"), "sales", ["studio_id"], unique=False)
    op.create_index(op.f("ix_sales_client_id"), "sales", ["client_id"], unique=False)
    op.create_index(
        op.f("ix_sales_professional_id"), "sales", ["professional_id"], unique=False
    )
    op.create_index(
        "ix_sales_studio_comp_status",
        "sales",
        ["studio_id", "competence_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_sales_studio_appt", "sales", ["studio_id", "appointment_id"], unique=False
    )

    op.create_table(
        "sale_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=30), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("professional_id", sa.Uuid(), nullable=True),
        sa.Column("description_snapshot", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "unit_cost_snapshot", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "total_item_amount", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_sale_items_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_price >= 0", name=op.f("ck_sale_items_unit_price_non_negative")
        ),
        sa.CheckConstraint(
            "unit_cost_snapshot >= 0",
            name=op.f("ck_sale_items_unit_cost_non_negative"),
        ),
        sa.CheckConstraint(
            "discount_amount >= 0",
            name=op.f("ck_sale_items_item_discount_non_negative"),
        ),
        sa.CheckConstraint(
            "total_item_amount >= 0",
            name=op.f("ck_sale_items_total_item_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_sale_items_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_sale_items_sale_id_sales"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["piercing_services.id"],
            name=op.f("fk_sale_items_service_id_piercing_services"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["piercing_products.id"],
            name=op.f("fk_sale_items_product_id_piercing_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["users.id"],
            name=op.f("fk_sale_items_professional_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_items")),
    )
    op.create_index(
        op.f("ix_sale_items_studio_id"), "sale_items", ["studio_id"], unique=False
    )
    op.create_index(
        op.f("ix_sale_items_professional_id"),
        "sale_items",
        ["professional_id"],
        unique=False,
    )
    op.create_index(
        "ix_sale_items_studio_sale", "sale_items", ["studio_id", "sale_id"], unique=False
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("is_deposit", sa.Boolean(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "fee_percentage_snapshot", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column(
            "fixed_fee_snapshot", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("fee_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "gross_amount > 0", name=op.f("ck_payments_payment_gross_positive")
        ),
        sa.CheckConstraint(
            "fee_amount >= 0", name=op.f("ck_payments_payment_fee_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_payments_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_payments_sale_id_sales"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_payments_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_payments_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index(
        op.f("ix_payments_studio_id"), "payments", ["studio_id"], unique=False
    )
    op.create_index(
        "ix_payments_studio_sale", "payments", ["studio_id", "sale_id"], unique=False
    )
    op.create_index(
        "ix_payments_studio_appt",
        "payments",
        ["studio_id", "appointment_id"],
        unique=False,
    )

    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("cash_flow_direction", sa.String(length=12), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fee_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("competence_date", sa.Date(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_sale_id", sa.Uuid(), nullable=True),
        sa.Column("reference_payment_id", sa.Uuid(), nullable=True),
        sa.Column("reference_appointment_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "gross_amount > 0",
            name=op.f("ck_financial_transactions_fin_tx_gross_positive"),
        ),
        sa.CheckConstraint(
            "fee_amount >= 0",
            name=op.f("ck_financial_transactions_fin_tx_fee_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_financial_transactions_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reference_sale_id"],
            ["sales.id"],
            name=op.f("fk_financial_transactions_reference_sale_id_sales"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reference_payment_id"],
            ["payments.id"],
            name=op.f("fk_financial_transactions_reference_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reference_appointment_id"],
            ["appointments.id"],
            name=op.f("fk_financial_transactions_reference_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_transaction_id"],
            ["financial_transactions.id"],
            name=op.f(
                "fk_financial_transactions_reversed_transaction_id_financial_transactions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_financial_transactions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_transactions")),
        sa.UniqueConstraint(
            "reversed_transaction_id",
            name=op.f("uq_financial_transactions_reversed_transaction_id"),
        ),
    )
    op.create_index(
        op.f("ix_financial_transactions_studio_id"),
        "financial_transactions",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        "ix_fin_tx_studio_comp_type",
        "financial_transactions",
        ["studio_id", "competence_date", "type", "category"],
        unique=False,
    )

    op.create_table(
        "commissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("sale_item_id", sa.Uuid(), nullable=True),
        sa.Column("item_kind", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "commission_pct_snapshot", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column(
            "commission_amount", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payout_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_commissions_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["users.id"],
            name=op.f("fk_commissions_professional_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_commissions_sale_id_sales"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_item_id"],
            ["sale_items.id"],
            name=op.f("fk_commissions_sale_item_id_sale_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["payout_transaction_id"],
            ["financial_transactions.id"],
            name=op.f("fk_commissions_payout_transaction_id_financial_transactions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commissions")),
    )
    op.create_index(
        op.f("ix_commissions_studio_id"), "commissions", ["studio_id"], unique=False
    )
    op.create_index(
        "ix_commissions_studio_prof_status",
        "commissions",
        ["studio_id", "professional_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_commissions_studio_sale", "commissions", ["studio_id", "sale_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("commissions")
    op.drop_table("financial_transactions")
    op.drop_table("payments")
    op.drop_table("sale_items")
    op.drop_table("sales")
