from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import (
    AuditAction,
    InventoryMovementType,
    PiercingItemType,
    StudioRole,
)
from app.core.exceptions import ConflictError, DomainValidationError
from app.core.rbac import TenantContext
from app.core.timezone import utcnow
from app.domains.piercing.inventory.models import InventoryMovement, PiercingProduct
from app.domains.piercing.inventory.repository import (
    InventoryMovementRepository,
    PiercingProductRepository,
)
from app.domains.piercing.inventory.schemas import (
    InventoryMovementCreateRequest,
    InventoryMovementOwnerResponse,
    InventoryMovementStaffResponse,
    PiercingProductCreateRequest,
    PiercingProductOwnerResponse,
    PiercingProductStaffResponse,
    PiercingProductUpdateRequest,
)


def serialize_product_for_role(
    product: PiercingProduct, role: StudioRole
) -> PiercingProductOwnerResponse | PiercingProductStaffResponse:
    is_low_stock = product.stock_quantity <= product.min_stock_alert
    common = {
        "id": product.id,
        "studio_id": product.studio_id,
        "sku": product.sku,
        "name": product.name,
        "item_type": product.item_type,
        "category_site": product.category_site,
        "material": product.material,
        "threading_type": product.threading_type,
        "gauge_thickness": product.gauge_thickness,
        "length_diameter": product.length_diameter,
        "sale_price": product.sale_price,
        "stock_quantity": product.stock_quantity,
        "min_stock_alert": product.min_stock_alert,
        "is_low_stock": is_low_stock,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }
    if role == StudioRole.OWNER:
        return PiercingProductOwnerResponse(**common, cost_price=product.cost_price)
    return PiercingProductStaffResponse(**common)


def serialize_movement_for_role(
    mov: InventoryMovement, role: StudioRole
) -> InventoryMovementOwnerResponse | InventoryMovementStaffResponse:
    common = {
        "id": mov.id,
        "studio_id": mov.studio_id,
        "product_id": mov.product_id,
        "movement_type": mov.movement_type,
        "quantity_delta": mov.quantity_delta,
        "resulting_stock": mov.resulting_stock,
        "reference_sale_id": mov.reference_sale_id,
        "reason": mov.reason,
        "created_by": mov.created_by,
        "created_at": mov.created_at,
    }
    if role == StudioRole.OWNER:
        return InventoryMovementOwnerResponse(
            **common, unit_cost_snapshot=mov.unit_cost_snapshot
        )
    return InventoryMovementStaffResponse(**common)


def _validate_movement_delta_by_type(
    movement_type: InventoryMovementType, quantity_delta: int
) -> None:
    if quantity_delta == 0:
        raise DomainValidationError(
            detail="A quantidade movimentada deve ser diferente de zero.",
            code="INVALID_MOVEMENT_QUANTITY",
        )
    if (
        movement_type
        in {InventoryMovementType.IN_PURCHASE, InventoryMovementType.RETURN_REFUND}
        and quantity_delta < 0
    ):
        raise DomainValidationError(
            detail="Movimentos de entrada (IN_PURCHASE / RETURN_REFUND) exigem quantidade positiva.",
            code="POSITIVE_DELTA_REQUIRED",
        )
    if movement_type == InventoryMovementType.OUT_SALE and quantity_delta > 0:
        raise DomainValidationError(
            detail="Movimentos de saída por venda (OUT_SALE) exigem quantidade negativa.",
            code="NEGATIVE_DELTA_REQUIRED",
        )


async def list_products(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    q: str | None = None,
    item_type: PiercingItemType | None = None,
    material: str | None = None,
    gauge_thickness: str | None = None,
    length_diameter: str | None = None,
    low_stock_only: bool = False,
    active_only: bool = False,
) -> list[PiercingProductOwnerResponse | PiercingProductStaffResponse]:
    repo = PiercingProductRepository(session, tenant.studio_id)
    rows = await repo.search(
        q=q,
        item_type=item_type,
        material=material,
        gauge_thickness=gauge_thickness,
        length_diameter=length_diameter,
        low_stock_only=low_stock_only,
        active_only=active_only,
    )
    return [serialize_product_for_role(p, tenant.role) for p in rows]


async def get_product(
    session: AsyncSession,
    tenant: TenantContext,
    product_id: uuid.UUID,
) -> PiercingProductOwnerResponse | PiercingProductStaffResponse:
    repo = PiercingProductRepository(session, tenant.studio_id)
    product = await repo.get_by_id_or_404(
        product_id, detail="Produto ou joia não encontrado."
    )
    return serialize_product_for_role(product, tenant.role)


async def create_product(
    session: AsyncSession,
    tenant: TenantContext,
    payload: PiercingProductCreateRequest,
    *,
    request: Request | None = None,
) -> PiercingProductOwnerResponse:
    product_repo = PiercingProductRepository(session, tenant.studio_id)
    mov_repo = InventoryMovementRepository(session, tenant.studio_id)

    if payload.sku:
        existing_sku = await product_repo.get_active_by_sku(payload.sku)
        if existing_sku is not None:
            raise ConflictError(
                detail=f"Já existe um produto ativo com o SKU '{payload.sku}' neste estúdio.",
                code="PRODUCT_SKU_ALREADY_EXISTS",
            )

    product = PiercingProduct(
        studio_id=tenant.studio_id,
        sku=payload.sku,
        name=payload.name.strip(),
        item_type=payload.item_type,
        category_site=payload.category_site,
        material=payload.material,
        threading_type=payload.threading_type,
        gauge_thickness=payload.gauge_thickness,
        length_diameter=payload.length_diameter,
        cost_price=payload.cost_price,
        sale_price=payload.sale_price,
        stock_quantity=payload.initial_stock,
        min_stock_alert=payload.min_stock_alert,
        is_active=payload.is_active,
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )

    try:
        await product_repo.add(product)
        if payload.initial_stock > 0:
            init_type = InventoryMovementType(payload.initial_movement_type)
            await mov_repo.add(
                InventoryMovement(
                    studio_id=tenant.studio_id,
                    product_id=product.id,
                    movement_type=init_type,
                    quantity_delta=payload.initial_stock,
                    resulting_stock=payload.initial_stock,
                    unit_cost_snapshot=product.cost_price,
                    reason="Saldo inicial de cadastro",
                    created_by=tenant.user_id,
                )
            )

        await record_audit_log(
            session,
            studio_id=tenant.studio_id,
            actor_user_id=tenant.user_id,
            entity_name="piercing_products",
            entity_id=product.id,
            action=AuditAction.CREATE,
            metadata_diff={
                "name": product.name,
                "sku": product.sku,
                "initial_stock": product.stock_quantity,
            },
            request=request,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            detail="Conflito ao salvar produto (verifique se o SKU já está em uso).",
            code="PRODUCT_SKU_ALREADY_EXISTS",
        ) from exc

    await session.refresh(product)
    return PiercingProductOwnerResponse.model_validate(
        serialize_product_for_role(product, StudioRole.OWNER)
    )


async def update_product(
    session: AsyncSession,
    tenant: TenantContext,
    product_id: uuid.UUID,
    payload: PiercingProductUpdateRequest,
    *,
    request: Request | None = None,
) -> PiercingProductOwnerResponse:
    product_repo = PiercingProductRepository(session, tenant.studio_id)
    existing = await product_repo.get_by_id_or_404(
        product_id, detail="Produto ou joia não encontrado."
    )

    changes = payload.model_dump(exclude_unset=True)
    # Defesa extra: jamais permitir stock_quantity em update cadastral
    changes.pop("stock_quantity", None)
    if not changes:
        return PiercingProductOwnerResponse.model_validate(
            serialize_product_for_role(existing, StudioRole.OWNER)
        )

    if "sku" in changes and changes["sku"] and changes["sku"] != existing.sku:
        dup = await product_repo.get_active_by_sku(
            changes["sku"], exclude_product_id=product_id
        )
        if dup is not None:
            raise ConflictError(
                detail=f"Já existe outro produto ativo com o SKU '{changes['sku']}'.",
                code="PRODUCT_SKU_ALREADY_EXISTS",
            )

    if "name" in changes and changes["name"]:
        changes["name"] = changes["name"].strip()
    changes["updated_by"] = tenant.user_id

    try:
        updated = await product_repo.update_by_id(product_id, changes)
        await record_audit_log(
            session,
            studio_id=tenant.studio_id,
            actor_user_id=tenant.user_id,
            entity_name="piercing_products",
            entity_id=product_id,
            action=AuditAction.UPDATE,
            metadata_diff={
                k: str(v) for k, v in changes.items() if k != "updated_by"
            },
            request=request,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            detail="SKU já utilizado por outro produto neste estúdio.",
            code="PRODUCT_SKU_ALREADY_EXISTS",
        ) from exc

    await session.refresh(updated)
    return PiercingProductOwnerResponse.model_validate(
        serialize_product_for_role(updated, StudioRole.OWNER)
    )


async def soft_delete_product(
    session: AsyncSession,
    tenant: TenantContext,
    product_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    product_repo = PiercingProductRepository(session, tenant.studio_id)
    product = await product_repo.get_by_id_or_404(
        product_id, detail="Produto ou joia não encontrado."
    )
    await product_repo.soft_delete_by_id(product.id, actor_user_id=tenant.user_id)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="piercing_products",
        entity_id=product.id,
        action=AuditAction.SOFT_DELETE,
        metadata_diff={"name": product.name, "sku": product.sku},
        request=request,
    )
    await session.commit()


async def register_inventory_movement(
    session: AsyncSession,
    tenant: TenantContext,
    product_id: uuid.UUID,
    payload: InventoryMovementCreateRequest,
    *,
    request: Request | None = None,
) -> InventoryMovementOwnerResponse:
    _validate_movement_delta_by_type(payload.movement_type, payload.quantity_delta)

    product_repo = PiercingProductRepository(session, tenant.studio_id)
    mov_repo = InventoryMovementRepository(session, tenant.studio_id)

    # Lock transacional pessimista (SELECT ... FOR UPDATE) impedindo corrida de saldo
    product = await product_repo.get_by_id_for_update_or_404(product_id)

    new_stock = product.stock_quantity + payload.quantity_delta
    if new_stock < 0:
        raise DomainValidationError(
            detail=(
                f"Saldo insuficiente em estoque. Atual: {product.stock_quantity}, "
                f"movimentação solicitada: {payload.quantity_delta}."
            ),
            code="INSUFFICIENT_STOCK",
        )

    effective_unit_cost = (
        payload.unit_cost
        if payload.unit_cost is not None
        and payload.movement_type == InventoryMovementType.IN_PURCHASE
        else product.cost_price
    )

    if (
        payload.unit_cost is not None
        and payload.movement_type == InventoryMovementType.IN_PURCHASE
    ):
        product.cost_price = payload.unit_cost

    product.stock_quantity = new_stock
    product.updated_by = tenant.user_id
    product.updated_at = utcnow()

    movement = await mov_repo.add(
        InventoryMovement(
            studio_id=tenant.studio_id,
            product_id=product.id,
            movement_type=payload.movement_type,
            quantity_delta=payload.quantity_delta,
            resulting_stock=new_stock,
            unit_cost_snapshot=effective_unit_cost,
            reason=payload.reason.strip(),
            created_by=tenant.user_id,
        )
    )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="inventory_movements",
        entity_id=movement.id,
        action=AuditAction.INVENTORY_MOVEMENT,
        metadata_diff={
            "product_id": str(product.id),
            "movement_type": movement.movement_type.value,
            "quantity_delta": movement.quantity_delta,
            "resulting_stock": new_stock,
            "reason": movement.reason,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(movement)
    return InventoryMovementOwnerResponse.model_validate(
        serialize_movement_for_role(movement, StudioRole.OWNER)
    )


async def list_product_movements(
    session: AsyncSession,
    tenant: TenantContext,
    product_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[InventoryMovementOwnerResponse | InventoryMovementStaffResponse]:
    product_repo = PiercingProductRepository(session, tenant.studio_id)
    # Garante 404 anti-IDOR caso o product_id pertença a outro estúdio ou não exista
    await product_repo.get_by_id_or_404(
        product_id, detail="Produto ou joia não encontrado."
    )
    mov_repo = InventoryMovementRepository(session, tenant.studio_id)
    rows = await mov_repo.list_by_product(product_id, limit=limit)
    return [serialize_movement_for_role(m, tenant.role) for m in rows]
