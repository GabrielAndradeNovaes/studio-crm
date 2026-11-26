from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.module_guard import require_module
from app.core.rbac import TenantContext

router = APIRouter(
    prefix="/tattoo",
    tags=["Module: Tattoo (Future)"],
    dependencies=[Depends(require_module("tattoo"))],
)


@router.get("/module-status")
async def get_tattoo_module_status(
    tenant: TenantContext = Depends(require_module("tattoo")),
) -> dict[str, object]:
    return {
        "module": "tattoo",
        "enabled": True,
        "studio_id": str(tenant.studio_id),
        "features": ["tattoo_sessions", "flash_catalog", "custom_quotes"],
    }
