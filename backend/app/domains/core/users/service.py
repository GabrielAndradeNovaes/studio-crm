from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import AuditAction, StudioRole
from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.rbac import TenantContext
from app.core.security import hash_password
from app.domains.core.users.models import StudioMembership, User
from app.domains.core.users.repository import (
    StudioMembershipRepository,
    get_user_by_email,
    get_user_by_id,
)
from app.domains.core.users.schemas import (
    TeamMemberCreateRequest,
    TeamMemberDirectoryResponse,
    TeamMemberOwnerResponse,
    TeamMemberUpdateRequest,
)


def _to_owner_response(membership: StudioMembership, user: User) -> TeamMemberOwnerResponse:
    return TeamMemberOwnerResponse(
        membership_id=membership.id,
        studio_id=membership.studio_id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=membership.role,
        commission_service_pct=membership.commission_service_pct,
        commission_product_pct=membership.commission_product_pct,
        is_active=membership.is_active and user.is_active,
        created_at=membership.created_at,
    )


async def get_my_membership_profile(
    session: AsyncSession, tenant: TenantContext
) -> TeamMemberOwnerResponse:
    repo = StudioMembershipRepository(session, tenant.studio_id)
    membership = await repo.get_by_user_id(tenant.user_id)
    user = await get_user_by_id(session, tenant.user_id)
    if membership is None or user is None:
        raise NotFoundError(detail="Vínculo de equipe não encontrado.")
    return _to_owner_response(membership, user)


async def list_team_for_owner(
    session: AsyncSession, tenant: TenantContext
) -> list[TeamMemberOwnerResponse]:
    repo = StudioMembershipRepository(session, tenant.studio_id)
    rows = await repo.list_with_users(active_only=False)
    return [_to_owner_response(m, u) for m, u in rows]


async def list_team_directory(
    session: AsyncSession, tenant: TenantContext
) -> list[TeamMemberDirectoryResponse]:
    repo = StudioMembershipRepository(session, tenant.studio_id)
    rows = await repo.list_with_users(active_only=True)
    return [
        TeamMemberDirectoryResponse(
            membership_id=m.id,
            studio_id=m.studio_id,
            user_id=u.id,
            name=u.name,
            email=u.email,
            role=m.role,
            is_active=m.is_active and u.is_active,
        )
        for m, u in rows
    ]


async def add_team_member(
    session: AsyncSession,
    tenant: TenantContext,
    payload: TeamMemberCreateRequest,
    *,
    request: Request | None = None,
) -> TeamMemberOwnerResponse:
    repo = StudioMembershipRepository(session, tenant.studio_id)
    email = payload.email.strip().lower()

    user = await get_user_by_email(session, email)
    if user is None:
        if not payload.password:
            raise DomainValidationError(
                detail="Informe uma senha inicial para cadastrar um novo usuário.",
                code="PASSWORD_REQUIRED_FOR_NEW_USER",
            )
        user = User(
            name=payload.name.strip(),
            email=email,
            password_hash=hash_password(payload.password),
            is_superadmin=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    else:
        existing_membership = await repo.get_by_user_id(user.id)
        if existing_membership is not None:
            raise ConflictError(
                detail="Este usuário já faz parte da equipe deste estúdio.",
                code="MEMBER_ALREADY_EXISTS",
            )

    membership = await repo.add(
        StudioMembership(
            studio_id=tenant.studio_id,
            user_id=user.id,
            role=payload.role,
            commission_service_pct=payload.commission_service_pct,
            commission_product_pct=payload.commission_product_pct,
            is_active=True,
        )
    )

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="studio_memberships",
        entity_id=membership.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "user_id": str(user.id),
            "email": user.email,
            "role": membership.role.value,
            "commission_service_pct": str(membership.commission_service_pct),
            "commission_product_pct": str(membership.commission_product_pct),
        },
        request=request,
    )
    await session.commit()
    await session.refresh(membership)
    return _to_owner_response(membership, user)


async def update_team_member(
    session: AsyncSession,
    tenant: TenantContext,
    membership_id: uuid.UUID,
    payload: TeamMemberUpdateRequest,
    *,
    request: Request | None = None,
) -> TeamMemberOwnerResponse:
    repo = StudioMembershipRepository(session, tenant.studio_id)
    current = await repo.get_by_id_or_404(membership_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        user = await get_user_by_id(session, current.user_id)
        if user is None:
            raise NotFoundError(detail="Usuário não encontrado.")
        return _to_owner_response(current, user)

    # Impede remover ou rebaixar o último OWNER ativo do estúdio
    will_lose_owner_privilege = current.role == StudioRole.OWNER and (
        ("role" in changes and changes["role"] != StudioRole.OWNER)
        or ("is_active" in changes and changes["is_active"] is False)
    )
    if will_lose_owner_privilege and current.is_active:
        remaining_owners = await repo.count_active_owners(exclude_membership_id=current.id)
        if remaining_owners == 0:
            raise DomainValidationError(
                detail="O estúdio deve manter pelo menos um proprietário (OWNER) ativo.",
                code="LAST_OWNER_PROTECTED",
            )

    updated = await repo.update_by_id(membership_id, changes)
    user = await get_user_by_id(session, updated.user_id)
    if user is None:
        raise NotFoundError(detail="Usuário não encontrado.")

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="studio_memberships",
        entity_id=membership_id,
        action=AuditAction.UPDATE,
        metadata_diff={
            k: (v.value if hasattr(v, "value") else str(v)) for k, v in changes.items()
        },
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return _to_owner_response(updated, user)


async def deactivate_team_member(
    session: AsyncSession,
    tenant: TenantContext,
    membership_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    await update_team_member(
        session,
        tenant,
        membership_id,
        TeamMemberUpdateRequest(is_active=False),
        request=request,
    )
