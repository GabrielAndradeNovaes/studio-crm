from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    SoftDeleteMixin,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import InventoryMovementType, PiercingItemType
from app.core.timezone import utcnow


class PiercingProduct(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditActorsMixin,
    Base,
):
    __tablename__ = "piercing_products"
    __table_args__ = (
        Index("ix_piercing_products_studio_type", "studio_id", "item_type"),
        Index("ix_piercing_products_studio_material", "studio_id", "material"),
        Index(
            "uq_piercing_products_studio_sku_active",
            "studio_id",
            "sku",
            unique=True,
            postgresql_where=sa.text("sku IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=sa.text("sku IS NOT NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint("cost_price >= 0", name="cost_price_non_negative"),
        CheckConstraint("sale_price >= 0", name="sale_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="stock_quantity_non_negative"),
        CheckConstraint("min_stock_alert >= 0", name="min_stock_alert_non_negative"),
    )

    sku: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    item_type: Mapped[PiercingItemType] = mapped_column(
        Enum(PiercingItemType, name="piercing_item_type_enum", native_enum=False),
        default=PiercingItemType.JEWELRY,
        nullable=False,
    )
    category_site: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    threading_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gauge_thickness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    length_diameter: Mapped[str | None] = mapped_column(String(32), nullable=True)

    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_stock_alert: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryMovement(UUIDPrimaryKeyMixin, TenantModelMixin, Base):
    """
    Kardex imutável (append-only) de rastreabilidade de joias e insumos.
    Nenhuma linha deve ser editada ou apagada; reversões geram novo movimento.
    """

    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index(
            "ix_inventory_movements_studio_product_created",
            "studio_id",
            "product_id",
            "created_at",
        ),
        CheckConstraint("quantity_delta != 0", name="quantity_delta_non_zero"),
        CheckConstraint("resulting_stock >= 0", name="resulting_stock_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(
            InventoryMovementType,
            name="inventory_movement_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference_sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
