from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from app.core.enums import PiercingItemType
from app.core.exceptions import NotFoundError
from app.core.tenancy import BaseTenantRepository
from app.domains.piercing.inventory.models import InventoryMovement, PiercingProduct


class PiercingProductRepository(BaseTenantRepository[PiercingProduct]):
    model = PiercingProduct

    async def get_active_by_sku(
        self, sku: str, *, exclude_product_id: uuid.UUID | None = None
    ) -> PiercingProduct | None:
        stmt = self._base_select(include_deleted=False).where(
            PiercingProduct.sku == sku
        )
        if exclude_product_id is not None:
            stmt = stmt.where(PiercingProduct.id != exclude_product_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_update_or_404(
        self, product_id: uuid.UUID
    ) -> PiercingProduct:
        stmt = (
            self._base_select(include_deleted=False)
            .where(PiercingProduct.id == product_id)
            .with_for_update()
        )
        product = (await self.session.execute(stmt)).scalar_one_or_none()
        if product is None:
            raise NotFoundError(detail="Produto ou joia não encontrado.")
        return product

    async def search(
        self,
        *,
        q: str | None = None,
        item_type: PiercingItemType | None = None,
        material: str | None = None,
        gauge_thickness: str | None = None,
        length_diameter: str | None = None,
        low_stock_only: bool = False,
        active_only: bool = False,
    ) -> Sequence[PiercingProduct]:
        stmt = self._base_select(include_deleted=False)

        if q and q.strip():
            term = q.strip()
            stmt = stmt.where(
                sa.or_(
                    PiercingProduct.name.ilike(f"%{term}%"),
                    PiercingProduct.sku.ilike(f"%{term}%"),
                    PiercingProduct.category_site.ilike(f"%{term}%"),
                )
            )
        if item_type is not None:
            stmt = stmt.where(PiercingProduct.item_type == item_type)
        if material and material.strip():
            stmt = stmt.where(PiercingProduct.material.ilike(f"%{material.strip()}%"))
        if gauge_thickness and gauge_thickness.strip():
            stmt = stmt.where(
                PiercingProduct.gauge_thickness.ilike(gauge_thickness.strip())
            )
        if length_diameter and length_diameter.strip():
            stmt = stmt.where(
                PiercingProduct.length_diameter.ilike(length_diameter.strip())
            )
        if low_stock_only:
            stmt = stmt.where(
                PiercingProduct.stock_quantity <= PiercingProduct.min_stock_alert
            )
        if active_only:
            stmt = stmt.where(PiercingProduct.is_active.is_(True))

        stmt = stmt.order_by(PiercingProduct.name.asc())
        return (await self.session.execute(stmt)).scalars().all()


class InventoryMovementRepository(BaseTenantRepository[InventoryMovement]):
    model = InventoryMovement

    async def list_by_product(
        self, product_id: uuid.UUID, *, limit: int = 100
    ) -> Sequence[InventoryMovement]:
        stmt = (
            self._base_select()
            .where(InventoryMovement.product_id == product_id)
            .order_by(InventoryMovement.created_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()
