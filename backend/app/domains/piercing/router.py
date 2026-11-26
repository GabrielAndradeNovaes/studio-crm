from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.module_guard import require_module
from app.core.rbac import TenantContext

router = APIRouter(
    prefix="/piercing",
    tags=["Module: Piercing"],
    dependencies=[Depends(require_module("piercing"))],
)


@router.get("/module-status")
async def get_piercing_module_status(
    tenant: TenantContext = Depends(require_module("piercing")),
) -> dict[str, object]:
    return {
        "module": "piercing",
        "enabled": True,
        "studio_id": str(tenant.studio_id),
        "features": ["services_catalog", "jewelry_inventory", "technical_procedures"],
    }
