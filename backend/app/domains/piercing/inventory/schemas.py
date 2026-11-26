from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import InventoryMovementType, PiercingItemType
from app.core.exceptions import DomainValidationError


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


class PiercingProductCreateRequest(BaseModel):
    sku: str | None = Field(default=None, max_length=60)
    name: str = Field(..., min_length=2, max_length=160)
    item_type: PiercingItemType = PiercingItemType.JEWELRY
    category_site: str | None = Field(default=None, max_length=80)
    material: str | None = Field(default=None, max_length=80)
    threading_type: str | None = Field(default=None, max_length=60)
    gauge_thickness: str | None = Field(default=None, max_length=32)
    length_diameter: str | None = Field(default=None, max_length=32)

    cost_price: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    sale_price: Decimal = Field(..., ge=Decimal("0.00"))
    initial_stock: int = Field(default=0, ge=0)
    initial_movement_type: Literal["IN_PURCHASE", "ADJUSTMENT"] = "IN_PURCHASE"
    min_stock_alert: int = Field(default=1, ge=0)
    is_active: bool = True

    @field_validator(
        "sku",
        "category_site",
        "material",
        "threading_type",
        "gauge_thickness",
        "length_diameter",
        mode="before",
    )
    @classmethod
    def normalize_blank_strings(cls, v: str | None) -> str | None:
        return _clean_optional_str(v)


class PiercingProductUpdateRequest(BaseModel):
    sku: str | None = Field(default=None, max_length=60)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    item_type: PiercingItemType | None = None
    category_site: str | None = Field(default=None, max_length=80)
    material: str | None = Field(default=None, max_length=80)
    threading_type: str | None = Field(default=None, max_length=60)
    gauge_thickness: str | None = Field(default=None, max_length=32)
    length_diameter: str | None = Field(default=None, max_length=32)
    cost_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    sale_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    min_stock_alert: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def forbid_direct_stock_quantity_edit(cls, data: Any) -> Any:
        if isinstance(data, dict) and "stock_quantity" in data:
            raise DomainValidationError(
                detail=(
                    "Alteração direta de stock_quantity é proibida. "
                    "Use o endpoint de movimentação de estoque (Kardex)."
                ),
                code="DIRECT_STOCK_EDIT_FORBIDDEN",
            )
        return data

    @field_validator(
        "sku",
        "category_site",
        "material",
        "threading_type",
        "gauge_thickness",
        "length_diameter",
        mode="before",
    )
    @classmethod
    def normalize_blank_strings(cls, v: str | None) -> str | None:
        return _clean_optional_str(v)


class InventoryMovementCreateRequest(BaseModel):
    movement_type: InventoryMovementType
    quantity_delta: int = Field(
        ...,
        description="Positivo para entradas (IN_PURCHASE/RETURN_REFUND) e positivo ou negativo para ADJUSTMENT.",
    )
    unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        description="Custo unitário opcional para atualizar o preço de custo em entradas de compra.",
    )
    reason: str = Field(..., min_length=2, max_length=255)


class PiercingProductStaffResponse(BaseModel):
    """DTO para RECEPTION e PROFESSIONAL — omite completamente `cost_price`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    sku: str | None
    name: str
    item_type: PiercingItemType
    category_site: str | None
    material: str | None
    threading_type: str | None
    gauge_thickness: str | None
    length_diameter: str | None
    sale_price: Decimal
    stock_quantity: int
    min_stock_alert: int
    is_low_stock: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PiercingProductOwnerResponse(PiercingProductStaffResponse):
    """DTO exclusivo para OWNER — inclui `cost_price`."""

    cost_price: Decimal


class InventoryMovementStaffResponse(BaseModel):
    """DTO de Kardex para RECEPTION e PROFESSIONAL — omite `unit_cost_snapshot`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: InventoryMovementType
    quantity_delta: int
    resulting_stock: int
    reference_sale_id: uuid.UUID | None
    reason: str
    created_by: uuid.UUID | None
    created_at: datetime


class InventoryMovementOwnerResponse(InventoryMovementStaffResponse):
    """DTO de Kardex exclusivo para OWNER — inclui `unit_cost_snapshot`."""

    unit_cost_snapshot: Decimal
