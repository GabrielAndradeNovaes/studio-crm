from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import sqlalchemy as sa
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import StudioRole, SubscriptionStatus
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_jwt_token
from app.core.tenancy import bypass_tenant_filter, tenant_scope

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: uuid.UUID
    email: str
    name: str
    is_superadmin: bool
    studio_id: uuid.UUID | None
    role: StudioRole | None


@dataclass(frozen=True)
class TenantContext:
    user_id: uuid.UUID
    email: str
    name: str
    is_superadmin: bool
    studio_id: uuid.UUID
    studio_name: str
    studio_slug: str
    timezone: str
    subscription_status: SubscriptionStatus
    enabled_modules: list[str]
    commission_deducts_payment_fee: bool
    role: StudioRole


def assert_studio_operational(
    *, is_active: bool, subscription_status: SubscriptionStatus
) -> None:
    """
    Bloqueia acesso operacional de estúdios inativos ou suspensos,
    retornando códigos claros para tratamento dedicado no frontend.
    """
    if not is_active:
        raise ForbiddenError(
            detail="Este estúdio está desativado no momento.",
            code="STUDIO_INACTIVE",
        )
    if subscription_status == SubscriptionStatus.SUSPENDED:
        raise ForbiddenError(
            detail="A assinatura deste estúdio está suspensa. Regularize o plano para retomar o acesso operacional.",
            code="STUDIO_SUSPENDED",
        )


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedPrincipal:
    from app.domains.core.users.models import User

    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(detail="Credenciais de autenticação ausentes.")

    payload = decode_jwt_token(credentials.credentials, expected_type="access")
    try:
        user_id = uuid.UUID(payload["sub"])
        studio_id = uuid.UUID(payload["studio_id"]) if payload.get("studio_id") else None
        role = StudioRole(payload["role"]) if payload.get("role") else None
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError(detail="Payload de token inválido.") from exc

    with bypass_tenant_filter():
        stmt = sa.select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise UnauthorizedError(detail="Usuário inativo ou inexistente.", code="USER_INACTIVE")

    return AuthenticatedPrincipal(
        user_id=user.id,
        email=user.email,
        name=user.name,
        is_superadmin=user.is_superadmin,
        studio_id=studio_id,
        role=role,
    )


async def require_superadmin(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    if not principal.is_superadmin:
        raise ForbiddenError(
            detail="Acesso restrito ao administrador global da plataforma.",
            code="SUPERADMIN_REQUIRED",
        )
    return principal


async def get_active_tenant_context(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TenantContext, None]:
    from app.domains.core.studios.models import Studio
    from app.domains.core.users.models import StudioMembership

    if principal.studio_id is None:
        raise ForbiddenError(
            detail="Nenhum estúdio ativo selecionado na sessão atual.",
            code="STUDIO_CONTEXT_REQUIRED",
        )

    with bypass_tenant_filter():
        studio = (
            await db.execute(sa.select(Studio).where(Studio.id == principal.studio_id))
        ).scalar_one_or_none()
        if studio is None:
            raise UnauthorizedError(detail="Estúdio não encontrado.", code="STUDIO_NOT_FOUND")

        membership = (
            await db.execute(
                sa.select(StudioMembership).where(
                    StudioMembership.studio_id == studio.id,
                    StudioMembership.user_id == principal.user_id,
                    StudioMembership.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    if membership is None:
        raise ForbiddenError(
            detail="Você não possui vínculo ativo com este estúdio.",
            code="MEMBERSHIP_INACTIVE",
        )

    assert_studio_operational(
        is_active=studio.is_active,
        subscription_status=studio.subscription_status,
    )

    context = TenantContext(
        user_id=principal.user_id,
        email=principal.email,
        name=principal.name,
        is_superadmin=principal.is_superadmin,
        studio_id=studio.id,
        studio_name=studio.name,
        studio_slug=studio.slug,
        timezone=studio.timezone,
        subscription_status=studio.subscription_status,
        enabled_modules=list(studio.enabled_modules or []),
        commission_deducts_payment_fee=studio.commission_deducts_payment_fee,
        role=membership.role,
    )

    # Ativa o ContextVar do tenant durante todo o ciclo de vida da requisição
    with tenant_scope(studio.id):
        yield context


def require_roles(*allowed_roles: StudioRole):
    allowed = set(allowed_roles)

    async def _role_guard(
        tenant: TenantContext = Depends(get_active_tenant_context),
    ) -> TenantContext:
        if tenant.role not in allowed:
            raise ForbiddenError(
                detail="Seu perfil não possui permissão para realizar esta operação.",
                code="INSUFFICIENT_ROLE",
            )
        return tenant

    return _role_guard
