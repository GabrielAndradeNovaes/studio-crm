from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.config import get_settings
from app.core.enums import AuditAction, SubscriptionStatus
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.rate_limit import get_client_ip
from app.core.rbac import AuthenticatedPrincipal, assert_studio_operational
from app.core.security import (
    clear_refresh_cookie,
    create_access_token,
    create_studio_selection_token,
    decode_jwt_token,
    generate_refresh_token_raw,
    hash_refresh_token,
    refresh_token_expires_at,
    set_refresh_cookie,
    verify_password,
)
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import utcnow
from app.domains.core.auth.models import RefreshToken
from app.domains.core.auth.schemas import (
    AuthenticatedUserSummary,
    AuthSessionResponse,
    LoginRequest,
    SelectStudioRequest,
    StudioMembershipOption,
    SwitchStudioRequest,
)
from app.domains.core.studios.models import Studio
from app.domains.core.users.models import StudioMembership, User
from app.domains.core.users.repository import (
    get_user_by_email,
    get_user_by_id,
    list_user_active_memberships_with_studios,
)


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _build_studio_option(membership: StudioMembership, studio: Studio) -> StudioMembershipOption:
    is_operational = (
        studio.is_active and studio.subscription_status != SubscriptionStatus.SUSPENDED
    )
    return StudioMembershipOption(
        studio_id=studio.id,
        studio_name=studio.name,
        studio_slug=studio.slug,
        role=membership.role,
        timezone=studio.timezone,
        enabled_modules=list(studio.enabled_modules or []),
        subscription_status=studio.subscription_status,
        is_studio_active=studio.is_active,
        is_operational=is_operational,
    )


def _build_user_summary(user: User) -> AuthenticatedUserSummary:
    return AuthenticatedUserSummary(
        id=user.id,
        name=user.name,
        email=user.email,
        is_superadmin=user.is_superadmin,
    )


async def _issue_full_session(
    session: AsyncSession,
    *,
    user: User,
    selected_pair: tuple[StudioMembership, Studio] | None,
    all_options: list[StudioMembershipOption],
    response: Response,
    request: Request,
    family_id: uuid.UUID | None = None,
) -> AuthSessionResponse:
    membership = selected_pair[0] if selected_pair else None
    studio = selected_pair[1] if selected_pair else None

    access_token, expires_in = create_access_token(
        user_id=user.id,
        studio_id=studio.id if studio else None,
        role=membership.role if membership else None,
        is_superadmin=user.is_superadmin,
        enabled_modules=list(studio.enabled_modules or []) if studio else [],
    )

    raw_refresh = generate_refresh_token_raw()
    refresh_record = RefreshToken(
        studio_id=studio.id if studio else None,
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=refresh_token_expires_at(),
        ip_address=get_client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:512] or None),
    )
    session.add(refresh_record)
    set_refresh_cookie(response, raw_refresh)

    current_option = _build_studio_option(membership, studio) if membership and studio else None
    return AuthSessionResponse(
        requires_studio_selection=False,
        selection_token=None,
        access_token=access_token,
        expires_in=expires_in,
        user=_build_user_summary(user),
        current_studio=current_option,
        available_studios=all_options,
    )


async def login_user(
    session: AsyncSession,
    payload: LoginRequest,
    *,
    request: Request,
    response: Response,
) -> AuthSessionResponse:
    user = await get_user_by_email(session, payload.email)
    password_ok = verify_password(
        payload.password, user.password_hash if user is not None else None
    )
    if user is None or not password_ok:
        raise UnauthorizedError(
            detail="E-mail ou senha inválidos.", code="INVALID_CREDENTIALS"
        )
    if not user.is_active:
        raise ForbiddenError(detail="Conta de usuário desativada.", code="USER_INACTIVE")

    user.last_login_at = utcnow()
    pairs = list(await list_user_active_memberships_with_studios(session, user.id))
    options = [_build_studio_option(m, s) for m, s in pairs]

    # Caso 1: Nenhum estúdio vinculado
    if len(pairs) == 0:
        if user.is_superadmin:
            result = await _issue_full_session(
                session,
                user=user,
                selected_pair=None,
                all_options=[],
                response=response,
                request=request,
            )
            await record_audit_log(
                session,
                studio_id=None,
                actor_user_id=user.id,
                entity_name="users",
                entity_id=user.id,
                action=AuditAction.LOGIN,
                metadata_diff={"context": "superadmin_global"},
                request=request,
            )
            await session.commit()
            return result

        raise ForbiddenError(
            detail="Você não possui vínculo ativo com nenhum estúdio.",
            code="NO_ACTIVE_STUDIO_MEMBERSHIP",
        )

    # Caso 2: Exatamente 1 vínculo ativo -> login direto para esse studio_id
    if len(pairs) == 1:
        membership, studio = pairs[0]
        is_op = studio.is_active and studio.subscription_status != SubscriptionStatus.SUSPENDED
        if not is_op:
            if user.is_superadmin:
                result = await _issue_full_session(
                    session,
                    user=user,
                    selected_pair=None,
                    all_options=options,
                    response=response,
                    request=request,
                )
                await session.commit()
                return result
            assert_studio_operational(
                is_active=studio.is_active,
                subscription_status=studio.subscription_status,
            )

        result = await _issue_full_session(
            session,
            user=user,
            selected_pair=(membership, studio),
            all_options=options,
            response=response,
            request=request,
        )
        await record_audit_log(
            session,
            studio_id=studio.id,
            actor_user_id=user.id,
            entity_name="users",
            entity_id=user.id,
            action=AuditAction.LOGIN,
            metadata_diff={"role": membership.role.value},
            request=request,
        )
        await session.commit()
        return result

    # Caso 3: 2 ou mais vínculos ativos -> retorna lista para seleção de contexto
    operational_pairs = [
        (m, s)
        for m, s in pairs
        if s.is_active and s.subscription_status != SubscriptionStatus.SUSPENDED
    ]
    if not operational_pairs and not user.is_superadmin:
        # Propaga o código claro do primeiro estúdio bloqueado (SUSPENDED ou INACTIVE)
        first_studio = pairs[0][1]
        assert_studio_operational(
            is_active=first_studio.is_active,
            subscription_status=first_studio.subscription_status,
        )

    selection_token = create_studio_selection_token(user_id=user.id)
    await session.commit()
    return AuthSessionResponse(
        requires_studio_selection=True,
        selection_token=selection_token,
        access_token=None,
        expires_in=None,
        user=_build_user_summary(user),
        current_studio=None,
        available_studios=options,
    )


async def select_studio_session(
    session: AsyncSession,
    payload: SelectStudioRequest,
    *,
    request: Request,
    response: Response,
) -> AuthSessionResponse:
    token_data = decode_jwt_token(payload.selection_token, expected_type="studio_selection")
    user_id = uuid.UUID(token_data["sub"])

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError(detail="Usuário inativo ou inválido.", code="USER_INACTIVE")

    pairs = list(await list_user_active_memberships_with_studios(session, user.id))
    options = [_build_studio_option(m, s) for m, s in pairs]
    chosen = next(((m, s) for m, s in pairs if s.id == payload.studio_id), None)
    if chosen is None:
        raise ForbiddenError(
            detail="Você não possui vínculo ativo com o estúdio selecionado.",
            code="MEMBERSHIP_INACTIVE",
        )

    membership, studio = chosen
    assert_studio_operational(
        is_active=studio.is_active,
        subscription_status=studio.subscription_status,
    )

    result = await _issue_full_session(
        session,
        user=user,
        selected_pair=(membership, studio),
        all_options=options,
        response=response,
        request=request,
    )
    await record_audit_log(
        session,
        studio_id=studio.id,
        actor_user_id=user.id,
        entity_name="users",
        entity_id=user.id,
        action=AuditAction.LOGIN,
        metadata_diff={"selected_from_multi_studio": True, "role": membership.role.value},
        request=request,
    )
    await session.commit()
    return result


async def switch_studio_session(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    payload: SwitchStudioRequest,
    *,
    request: Request,
    response: Response,
) -> AuthSessionResponse:
    user = await get_user_by_id(session, principal.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError(detail="Usuário inativo.", code="USER_INACTIVE")

    pairs = list(await list_user_active_memberships_with_studios(session, user.id))
    options = [_build_studio_option(m, s) for m, s in pairs]
    chosen = next(((m, s) for m, s in pairs if s.id == payload.studio_id), None)
    if chosen is None:
        raise ForbiddenError(
            detail="Você não possui vínculo ativo com o estúdio solicitado.",
            code="MEMBERSHIP_INACTIVE",
        )

    membership, studio = chosen
    assert_studio_operational(
        is_active=studio.is_active,
        subscription_status=studio.subscription_status,
    )

    # Revoga refresh token anterior do cookie, se existir
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw_cookie:
        old_hash = hash_refresh_token(raw_cookie)
        with bypass_tenant_filter():
            await session.execute(
                sa.update(RefreshToken)
                .where(RefreshToken.token_hash == old_hash, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )

    result = await _issue_full_session(
        session,
        user=user,
        selected_pair=(membership, studio),
        all_options=options,
        response=response,
        request=request,
    )
    await record_audit_log(
        session,
        studio_id=studio.id,
        actor_user_id=user.id,
        entity_name="studio_memberships",
        entity_id=membership.id,
        action=AuditAction.SWITCH_STUDIO,
        metadata_diff={"previous_studio_id": str(principal.studio_id)},
        request=request,
    )
    await session.commit()
    return result


async def refresh_session_token(
    session: AsyncSession,
    *,
    request: Request,
    response: Response,
) -> AuthSessionResponse:
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_cookie:
        raise UnauthorizedError(
            detail="Refresh token ausente.", code="REFRESH_TOKEN_MISSING"
        )

    token_hash = hash_refresh_token(raw_cookie)
    with bypass_tenant_filter():
        record = (
            await session.execute(
                sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()

    if record is None:
        clear_refresh_cookie(response)
        raise UnauthorizedError(detail="Sessão inválida.", code="INVALID_REFRESH_TOKEN")

    now = utcnow()
    # Detecção de reuso de Refresh Token já rotacionado -> revoga toda a família!
    if record.revoked_at is not None:
        with bypass_tenant_filter():
            await session.execute(
                sa.update(RefreshToken)
                .where(
                    RefreshToken.family_id == record.family_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        await session.commit()
        clear_refresh_cookie(response)
        raise UnauthorizedError(
            detail="Sessão revogada por medida de segurança (reutilização de token detectada).",
            code="REFRESH_TOKEN_REUSED",
        )

    if _ensure_utc(record.expires_at) <= now:
        record.revoked_at = now
        await session.commit()
        clear_refresh_cookie(response)
        raise UnauthorizedError(
            detail="Sessão expirada. Faça login novamente.", code="REFRESH_TOKEN_EXPIRED"
        )

    user = await get_user_by_id(session, record.user_id)
    if user is None or not user.is_active:
        record.revoked_at = now
        await session.commit()
        clear_refresh_cookie(response)
        raise UnauthorizedError(detail="Usuário inativo.", code="USER_INACTIVE")

    pairs = list(await list_user_active_memberships_with_studios(session, user.id))
    options = [_build_studio_option(m, s) for m, s in pairs]

    selected_pair: tuple[StudioMembership, Studio] | None = None
    if record.studio_id is not None:
        selected_pair = next(((m, s) for m, s in pairs if s.id == record.studio_id), None)
        if selected_pair is None:
            record.revoked_at = now
            await session.commit()
            clear_refresh_cookie(response)
            raise ForbiddenError(
                detail="Seu vínculo com este estúdio foi encerrado.",
                code="MEMBERSHIP_INACTIVE",
            )
        assert_studio_operational(
            is_active=selected_pair[1].is_active,
            subscription_status=selected_pair[1].subscription_status,
        )
    elif not user.is_superadmin:
        record.revoked_at = now
        await session.commit()
        clear_refresh_cookie(response)
        raise ForbiddenError(
            detail="Sessão sem estúdio válida apenas para SuperAdmin.",
            code="STUDIO_CONTEXT_REQUIRED",
        )

    # Rotaciona o refresh token atual
    record.revoked_at = now
    result = await _issue_full_session(
        session,
        user=user,
        selected_pair=selected_pair,
        all_options=options,
        response=response,
        request=request,
        family_id=record.family_id,
    )
    await session.commit()
    return result


async def logout_user(
    session: AsyncSession,
    *,
    request: Request,
    response: Response,
) -> None:
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw_cookie:
        token_hash = hash_refresh_token(raw_cookie)
        with bypass_tenant_filter():
            record = (
                await session.execute(
                    sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash)
                )
            ).scalar_one_or_none()
            if record is not None:
                await session.execute(
                    sa.update(RefreshToken)
                    .where(
                        RefreshToken.family_id == record.family_id,
                        RefreshToken.revoked_at.is_(None),
                    )
                    .values(revoked_at=utcnow())
                )
                await session.commit()
    clear_refresh_cookie(response)


async def get_current_session_info(
    session: AsyncSession, principal: AuthenticatedPrincipal
) -> AuthSessionResponse:
    user = await get_user_by_id(session, principal.user_id)
    if user is None:
        raise UnauthorizedError(detail="Usuário não encontrado.")

    pairs = list(await list_user_active_memberships_with_studios(session, user.id))
    options = [_build_studio_option(m, s) for m, s in pairs]

    current_option: StudioMembershipOption | None = None
    if principal.studio_id is not None:
        chosen = next(((m, s) for m, s in pairs if s.id == principal.studio_id), None)
        if chosen is None:
            raise ForbiddenError(
                detail="Vínculo com o estúdio inativo.", code="MEMBERSHIP_INACTIVE"
            )
        assert_studio_operational(
            is_active=chosen[1].is_active,
            subscription_status=chosen[1].subscription_status,
        )
        current_option = _build_studio_option(chosen[0], chosen[1])

    return AuthSessionResponse(
        requires_studio_selection=False,
        user=_build_user_summary(user),
        current_studio=current_option,
        available_studios=options,
    )
