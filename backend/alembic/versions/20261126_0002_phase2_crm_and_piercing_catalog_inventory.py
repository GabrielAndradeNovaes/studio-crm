"""Phase 2: CRM clients, piercing_services, piercing_products and immutable inventory_movements (Kardex)

Revision ID: 20261126_0002
Revises: 20261126_0001
Create Date: 2026-11-26 11:25:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0002"
down_revision: Union[str, None] = "20261126_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("whatsapp", sa.String(length=24), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=True),
        sa.Column("lead_source", sa.String(length=20), nullable=False),
        sa.Column("tags", JSONVariant, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("guardian_name", sa.String(length=160), nullable=True),
        sa.Column("guardian_cpf", sa.String(length=14), nullable=True),
        sa.Column("guardian_whatsapp", sa.String(length=24), nullable=True),
        sa.Column("guardian_relationship", sa.String(length=60), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_clients_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_clients_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_clients_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_index(op.f("ix_clients_studio_id"), "clients", ["studio_id"], unique=False)
    op.create_index("ix_clients_studio_name", "clients", ["studio_id", "full_name"], unique=False)
    op.create_index(
        "uq_clients_studio_whatsapp_active",
        "clients",
        ["studio_id", "whatsapp"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "piercing_services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("anatomical_site", sa.String(length=80), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("base_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("return_days_downsize", sa.Integer(), nullable=True),
        sa.Column("aftercare_instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "duration_minutes > 0", name=op.f("ck_piercing_services_duration_positive")
        ),
        sa.CheckConstraint(
            "base_price >= 0", name=op.f("ck_piercing_services_base_price_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_piercing_services_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_piercing_services_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_piercing_services_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_piercing_services")),
    )
    op.create_index(
        op.f("ix_piercing_services_studio_id"),
        "piercing_services",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        "ix_piercing_services_studio_site",
        "piercing_services",
        ["studio_id", "anatomical_site"],
        unique=False,
    )

    op.create_table(
        "piercing_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(length=60), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("category_site", sa.String(length=80), nullable=True),
        sa.Column("material", sa.String(length=80), nullable=True),
        sa.Column("threading_type", sa.String(length=60), nullable=True),
        sa.Column("gauge_thickness", sa.String(length=32), nullable=True),
        sa.Column("length_diameter", sa.String(length=32), nullable=True),
        sa.Column("cost_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("min_stock_alert", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "cost_price >= 0", name=op.f("ck_piercing_products_cost_price_non_negative")
        ),
        sa.CheckConstraint(
            "sale_price >= 0", name=op.f("ck_piercing_products_sale_price_non_negative")
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_piercing_products_stock_quantity_non_negative"),
        ),
        sa.CheckConstraint(
            "min_stock_alert >= 0",
            name=op.f("ck_piercing_products_min_stock_alert_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_piercing_products_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_piercing_products_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_piercing_products_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_piercing_products")),
    )
    op.create_index(
        op.f("ix_piercing_products_studio_id"),
        "piercing_products",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        "ix_piercing_products_studio_type",
        "piercing_products",
        ["studio_id", "item_type"],
        unique=False,
    )
    op.create_index(
        "ix_piercing_products_studio_material",
        "piercing_products",
        ["studio_id", "material"],
        unique=False,
    )
    op.create_index(
        "uq_piercing_products_studio_sku_active",
        "piercing_products",
        ["studio_id", "sku"],
        unique=True,
        postgresql_where=sa.text("sku IS NOT NULL AND deleted_at IS NULL"),
        sqlite_where=sa.text("sku IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("resulting_stock", sa.Integer(), nullable=False),
        sa.Column("unit_cost_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reference_sale_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity_delta != 0",
            name=op.f("ck_inventory_movements_quantity_delta_non_zero"),
        ),
        sa.CheckConstraint(
            "resulting_stock >= 0",
            name=op.f("ck_inventory_movements_resulting_stock_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["piercing_products.id"],
            name=op.f("fk_inventory_movements_product_id_piercing_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_inventory_movements_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_inventory_movements_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_movements")),
    )
    op.create_index(
        op.f("ix_inventory_movements_studio_id"),
        "inventory_movements",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_movements_product_id"),
        "inventory_movements",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_studio_product_created",
        "inventory_movements",
        ["studio_id", "product_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_table("piercing_products")
    op.drop_table("piercing_services")
    op.drop_table("clients")
