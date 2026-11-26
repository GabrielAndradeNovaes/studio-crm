from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.config import get_settings
from app.core.enums import AuditAction, PaymentMethodCode, StudioRole, SubscriptionStatus
from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from app.core.rbac import AuthenticatedPrincipal, TenantContext
from app.core.security import hash_password, verify_password
from app.core.timezone import utcnow
from app.domains.core.anamnesis.service import ensure_default_piercing_template
from app.domains.core.studios.models import PaymentMethodConfig, Studio
from app.domains.core.studios.repository import (
    PaymentMethodConfigRepository,
    get_studio_by_id,
    get_studio_by_slug,
    list_all_studios,
)
from app.domains.core.studios.schemas import (
    PaymentMethodConfigUpdateRequest,
    StudioOnboardingRequest,
    StudioUpdateSettingsRequest,
    SuperadminCreateStudioRequest,
    SuperadminUpdateStudioGovernanceRequest,
)
from app.domains.core.users.models import StudioMembership, User
from app.domains.core.users.repository import get_user_by_email

DEFAULT_PAYMENT_METHODS: list[tuple[PaymentMethodCode, str, Decimal]] = [
    (PaymentMethodCode.PIX, "Pix", Decimal("0.00")),
    (PaymentMethodCode.CASH, "Dinheiro", Decimal("0.00")),
    (PaymentMethodCode.DEBIT_CARD, "Cartão de Débito", Decimal("1.99")),
    (PaymentMethodCode.CREDIT_CARD, "Cartão de Crédito", Decimal("3.99")),
]


def _slugify(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or f"studio-{secrets.token_hex(3)}"


async def _resolve_unique_slug(
    session: AsyncSession, *, requested_slug: str | None, studio_name: str
) -> str:
    if requested_slug:
        existing = await get_studio_by_slug(session, requested_slug)
        if existing is not None:
            raise ConflictError(
                detail=f"O identificador '{requested_slug}' já está em uso por outro estúdio.",
                code="SLUG_ALREADY_EXISTS",
            )
        return requested_slug

    base_slug = _slugify(studio_name)[:85]
    candidate = base_slug
    while await get_studio_by_slug(session, candidate) is not None:
        candidate = f"{base_slug}-{secrets.token_hex(2)}"
    return candidate


async def _seed_default_payment_methods(
    session: AsyncSession, studio_id: uuid.UUID
) -> None:
    repo = PaymentMethodConfigRepository(session, studio_id)
    for method_code, label, fee_pct in DEFAULT_PAYMENT_METHODS:
        await repo.add(
            PaymentMethodConfig(
                studio_id=studio_id,
                method=method_code,
                label=label,
                fee_percentage=fee_pct,
                fixed_fee=Decimal("0.00"),
                is_active=True,
            )
        )


async def onboard_studio_public(
    session: AsyncSession,
    payload: StudioOnboardingRequest,
    *,
    request: Request | None = None,
) -> Studio:
    settings = get_settings()
    if not settings.ALLOW_PUBLIC_ONBOARDING:
        raise ForbiddenError(
            detail="O cadastro público de novos estúdios está desativado. Contate o suporte comercial.",
            code="PUBLIC_ONBOARDING_DISABLED",
        )

    owner_email = payload.owner_email.strip().lower()
    existing_user = await get_user_by_email(session, owner_email)
    if existing_user is not None:
        if not verify_password(payload.owner_password, existing_user.password_hash):
            raise ConflictError(
                detail="Este e-mail já está cadastrado. Para criar uma nova filial/estúdio com ele, informe sua senha atual.",
                code="EMAIL_ALREADY_EXISTS",
            )
        owner_user = existing_user
    else:
        owner_user = User(
            name=payload.owner_name.strip(),
            email=owner_email,
            password_hash=hash_password(payload.owner_password),
            is_superadmin=False,
            is_active=True,
        )
        session.add(owner_user)
        await session.flush()

    slug = await _resolve_unique_slug(
        session, requested_slug=payload.slug, studio_name=payload.studio_name
    )
    now = utcnow()
    studio = Studio(
        name=payload.studio_name.strip(),
        slug=slug,
        document=payload.document,
        phone=payload.phone,
        plan_tier="piercing_mvp",
        enabled_modules=["piercing"],
        timezone=payload.timezone,
        subscription_status=SubscriptionStatus.TRIAL,
        trial_ends_at=now + timedelta(days=settings.DEFAULT_TRIAL_DAYS),
        commission_deducts_payment_fee=False,
        is_active=True,
    )
    session.add(studio)
    await session.flush()

    membership = StudioMembership(
        studio_id=studio.id,
        user_id=owner_user.id,
        role=StudioRole.OWNER,
        commission_service_pct=Decimal("0.00"),
        commission_product_pct=Decimal("0.00"),
        is_active=True,
    )
    session.add(membership)
    await _seed_default_payment_methods(session, studio.id)
    await ensure_default_piercing_template(
        session, studio.id, actor_user_id=owner_user.id
    )

    await record_audit_log(
        session,
        studio_id=studio.id,
        actor_user_id=owner_user.id,
        entity_name="studios",
        entity_id=studio.id,
        action=AuditAction.CREATE,
        metadata_diff={"onboarding": "public", "slug": studio.slug},
        request=request,
    )
    await session.commit()
    await session.refresh(studio)
    return studio


async def create_studio_by_superadmin(
    session: AsyncSession,
    payload: SuperadminCreateStudioRequest,
    *,
    actor: AuthenticatedPrincipal,
    request: Request | None = None,
) -> Studio:
    owner_email = payload.owner_email.strip().lower()
    existing_user = await get_user_by_email(session, owner_email)
    if existing_user is None:
        if not payload.owner_password:
            raise DomainValidationError(
                detail="A senha inicial do proprietário é obrigatória quando o e-mail ainda não possui conta na plataforma.",
                code="OWNER_PASSWORD_REQUIRED",
            )
        owner_user = User(
            name=payload.owner_name.strip(),
            email=owner_email,
            password_hash=hash_password(payload.owner_password),
            is_superadmin=False,
            is_active=True,
        )
        session.add(owner_user)
        await session.flush()
    else:
        owner_user = existing_user

    slug = await _resolve_unique_slug(
        session, requested_slug=payload.slug, studio_name=payload.name
    )
    trial_ends_at = (
        utcnow() + timedelta(days=payload.trial_days)
        if payload.subscription_status == SubscriptionStatus.TRIAL and payload.trial_days
        else None
    )
    studio = Studio(
        name=payload.name.strip(),
        slug=slug,
        document=payload.document,
        phone=payload.phone,
        plan_tier=payload.plan_tier,
        enabled_modules=payload.enabled_modules,
        timezone=payload.timezone,
        subscription_status=payload.subscription_status,
        trial_ends_at=trial_ends_at,
        commission_deducts_payment_fee=payload.commission_deducts_payment_fee,
        is_active=True,
    )
    session.add(studio)
    await session.flush()

    membership = StudioMembership(
        studio_id=studio.id,
        user_id=owner_user.id,
        role=StudioRole.OWNER,
        commission_service_pct=Decimal("0.00"),
        commission_product_pct=Decimal("0.00"),
        is_active=True,
    )
    session.add(membership)
    await _seed_default_payment_methods(session, studio.id)
    await ensure_default_piercing_template(
        session, studio.id, actor_user_id=owner_user.id
    )

    await record_audit_log(
        session,
        studio_id=studio.id,
        actor_user_id=actor.user_id,
        entity_name="studios",
        entity_id=studio.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "created_by_superadmin": True,
            "subscription_status": studio.subscription_status.value,
            "enabled_modules": studio.enabled_modules,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(studio)
    return studio


async def update_studio_governance_by_superadmin(
    session: AsyncSession,
    studio_id: uuid.UUID,
    payload: SuperadminUpdateStudioGovernanceRequest,
    *,
    actor: AuthenticatedPrincipal,
    request: Request | None = None,
) -> Studio:
    studio = await get_studio_by_id(session, studio_id)
    if studio is None:
        raise NotFoundError(detail="Estúdio não encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(studio, field, value)
    studio.updated_at = utcnow()

    await record_audit_log(
        session,
        studio_id=studio.id,
        actor_user_id=actor.user_id,
        entity_name="studios",
        entity_id=studio.id,
        action=AuditAction.UPDATE,
        metadata_diff={
            k: (v.value if hasattr(v, "value") else str(v)) for k, v in changes.items()
        },
        request=request,
    )
    await session.commit()
    await session.refresh(studio)
    return studio


async def get_current_studio_details(
    session: AsyncSession, tenant: TenantContext
) -> Studio:
    studio = await get_studio_by_id(session, tenant.studio_id)
    if studio is None:
        raise NotFoundError(detail="Estúdio não encontrado.")
    return studio


async def update_current_studio_settings(
    session: AsyncSession,
    tenant: TenantContext,
    payload: StudioUpdateSettingsRequest,
    *,
    request: Request | None = None,
) -> Studio:
    studio = await get_studio_by_id(session, tenant.studio_id)
    if studio is None:
        raise NotFoundError(detail="Estúdio não encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(studio, field, value)
    studio.updated_at = utcnow()

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="studios",
        entity_id=studio.id,
        action=AuditAction.UPDATE,
        metadata_diff=changes,
        request=request,
    )
    await session.commit()
    await session.refresh(studio)
    return studio


async def list_studio_payment_methods(
    session: AsyncSession, tenant: TenantContext
) -> list[PaymentMethodConfig]:
    repo = PaymentMethodConfigRepository(session, tenant.studio_id)
    return list(await repo.list_ordered())


async def update_studio_payment_method(
    session: AsyncSession,
    tenant: TenantContext,
    config_id: uuid.UUID,
    payload: PaymentMethodConfigUpdateRequest,
    *,
    request: Request | None = None,
) -> PaymentMethodConfig:
    repo = PaymentMethodConfigRepository(session, tenant.studio_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return await repo.get_by_id_or_404(config_id)

    updated = await repo.update_by_id(config_id, changes)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="payment_method_configs",
        entity_id=config_id,
        action=AuditAction.UPDATE,
        metadata_diff={k: str(v) for k, v in changes.items()},
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return updated


async def list_studios_superadmin(session: AsyncSession) -> list[Studio]:
    return list(await list_all_studios(session))
