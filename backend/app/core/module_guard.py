from __future__ import annotations

from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.core.rbac import TenantContext, get_active_tenant_context


def require_module(module_name: str):
    """
    Garante que o módulo solicitado (ex.: 'piercing' ou futuro 'tattoo')
    esteja habilitado em `studio.enabled_modules` para o tenant atual.
    """

    async def _module_guard(
        tenant: TenantContext = Depends(get_active_tenant_context),
    ) -> TenantContext:
        if module_name not in tenant.enabled_modules:
            raise ForbiddenError(
                detail=f"O módulo '{module_name}' não está habilitado para este estúdio.",
                code="MODULE_DISABLED",
            )
        return tenant

    return _module_guard
