from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import PiercingItemType, StudioRole
from app.core.module_guard import require_module
from app.core.rbac import TenantContext, require_roles
from app.domains.piercing.inventory.schemas import (
    InventoryMovementCreateRequest,
    InventoryMovementOwnerResponse,
    InventoryMovementStaffResponse,
    PiercingProductCreateRequest,
    PiercingProductOwnerResponse,
    PiercingProductStaffResponse,
    PiercingProductUpdateRequest,
)
from app.domains.piercing.inventory.service import (
    create_product,
    get_product,
    list_product_movements,
    list_products,
    register_inventory_movement,
    soft_delete_product,
    update_product,
)

router = APIRouter(
    prefix="/products",
    tags=["Module Piercing - Inventory & Kardex"],
    dependencies=[Depends(require_module("piercing"))],
)


@router.get(
    "",
    response_model=list[PiercingProductOwnerResponse | PiercingProductStaffResponse],
)
async def list_products_endpoint(
    q: str | None = Query(default=None, max_length=120),
    item_type: PiercingItemType | None = Query(default=None),
    material: str | None = Query(default=None, max_length=80),
    gauge_thickness: str | None = Query(default=None, max_length=32),
    length_diameter: str | None = Query(default=None, max_length=32),
    low_stock_only: bool = Query(default=False),
    active_only: bool = Query(default=False),
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    items = await list_products(
        db,
        tenant,
        q=q,
        item_type=item_type,
        material=material,
        gauge_thickness=gauge_thickness,
        length_diameter=length_diameter,
        low_stock_only=low_stock_only,
        active_only=active_only,
    )
    return JSONResponse(content=[item.model_dump(mode="json") for item in items])


@router.get(
    "/{product_id}",
    response_model=PiercingProductOwnerResponse | PiercingProductStaffResponse,
)
async def get_product_endpoint(
    product_id: uuid.UUID,
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    item = await get_product(db, tenant, product_id)
    return JSONResponse(content=item.model_dump(mode="json"))


@router.post(
    "",
    response_model=PiercingProductOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_endpoint(
    payload: PiercingProductCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> PiercingProductOwnerResponse:
    return await create_product(db, tenant, payload, request=request)


@router.patch("/{product_id}", response_model=PiercingProductOwnerResponse)
async def update_product_endpoint(
    product_id: uuid.UUID,
    payload: PiercingProductUpdateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> PiercingProductOwnerResponse:
    return await update_product(db, tenant, product_id, payload, request=request)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_endpoint(
    product_id: uuid.UUID,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await soft_delete_product(db, tenant, product_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{product_id}/movements",
    response_model=list[
        InventoryMovementOwnerResponse | InventoryMovementStaffResponse
    ],
)
async def list_movements_endpoint(
    product_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    tenant: TenantContext = Depends(require_module("piercing")),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    rows = await list_product_movements(db, tenant, product_id, limit=limit)
    return JSONResponse(content=[row.model_dump(mode="json") for row in rows])


@router.post(
    "/{product_id}/movements",
    response_model=InventoryMovementOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_movement_endpoint(
    product_id: uuid.UUID,
    payload: InventoryMovementCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> InventoryMovementOwnerResponse:
    return await register_inventory_movement(
        db, tenant, product_id, payload, request=request
    )
