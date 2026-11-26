from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import AuditAction, StudioRole
from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    GoneError,
    NotFoundError,
)
from app.core.rate_limit import get_client_ip
from app.core.rbac import TenantContext, assert_studio_operational
from app.core.tenancy import bypass_tenant_filter
from app.core.timezone import calculate_age_in_timezone, utcnow
from app.domains.core.anamnesis.defaults import (
    DEFAULT_PIERCING_CONSENT_TEXT,
    DEFAULT_PIERCING_FIELDS_SCHEMA,
    DEFAULT_PIERCING_TEMPLATE_TITLE,
)
from app.domains.core.anamnesis.models import (
    AnamnesisPublicLink,
    AnamnesisRecord,
    AnamnesisTemplate,
)
from app.domains.core.anamnesis.repository import (
    AnamnesisPublicLinkRepository,
    AnamnesisRecordRepository,
    AnamnesisTemplateRepository,
)
from app.domains.core.anamnesis.schemas import (
    AnamnesisRecordCreateRequest,
    AnamnesisRecordDetailResponse,
    AnamnesisRecordSummaryResponse,
    AnamnesisTemplateUpsertRequest,
    CreatePublicAnamnesisLinkRequest,
    PublicAnamnesisFormView,
    PublicAnamnesisLinkCreatedResponse,
    PublicAnamnesisSubmitRequest,
    PublicAnamnesisSubmittedResponse,
)
from app.domains.core.appointments.repository import AppointmentRepository
from app.domains.core.clients.models import Client
from app.domains.core.clients.repository import ClientRepository
from app.domains.core.studios.models import Studio


def _hash_public_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def ensure_default_piercing_template(
    session: AsyncSession, studio_id: uuid.UUID, *, actor_user_id: uuid.UUID | None = None
) -> AnamnesisTemplate:
    repo = AnamnesisTemplateRepository(session, studio_id)
    existing = await repo.get_active_for_module("piercing")
    if existing is not None:
        return existing

    template = AnamnesisTemplate(
        studio_id=studio_id,
        module="piercing",
        version=1,
        title=DEFAULT_PIERCING_TEMPLATE_TITLE,
        fields_schema=list(DEFAULT_PIERCING_FIELDS_SCHEMA),
        consent_text=DEFAULT_PIERCING_CONSENT_TEXT,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    await repo.add(template)
    return template


def _validate_answers_against_schema(
    fields_schema: list[dict[str, Any]], answers: dict[str, Any]
) -> None:
    missing: list[str] = []
    for field in fields_schema:
        key = field.get("key")
        if not key:
            continue
        if field.get("required"):
            val = answers.get(key)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                missing.append(field.get("label", key))
    if missing:
        raise DomainValidationError(
            detail=f"Preencha todas as perguntas obrigatórias da ficha ({len(missing)} pendente(s)).",
            code="ANAMNESIS_REQUIRED_FIELDS_MISSING",
        )


def _validate_consent_and_minor_signature(
    *,
    is_minor: bool,
    client: Client,
    consent_accepted: bool,
    guardian_signed_name: str | None,
    signature_payload: str,
) -> str | None:
    if not consent_accepted:
        raise DomainValidationError(
            detail="O aceite do termo de consentimento é obrigatório para registrar a ficha.",
            code="CONSENT_REQUIRED",
        )
    if not signature_payload or len(signature_payload.strip()) < 2:
        raise DomainValidationError(
            detail="A assinatura ou confirmação nominal é obrigatória.",
            code="SIGNATURE_REQUIRED",
        )
    cleaned_guardian = guardian_signed_name.strip() if guardian_signed_name else None
    if is_minor:
        if (
            not client.guardian_name
            or not client.guardian_cpf
            or not client.guardian_whatsapp
        ):
            raise DomainValidationError(
                detail="Cliente menor de 18 anos não possui dados completos do responsável legal no cadastro.",
                code="MINOR_GUARDIAN_REQUIRED",
            )
        if not cleaned_guardian or len(cleaned_guardian) < 3:
            raise DomainValidationError(
                detail="Para menores de 18 anos, a assinatura/identificação do responsável legal é obrigatória.",
                code="MINOR_GUARDIAN_SIGNATURE_REQUIRED",
            )
    return cleaned_guardian


async def list_templates(
    session: AsyncSession, tenant: TenantContext, *, module: str | None = None
) -> list[AnamnesisTemplate]:
    # Garante seed preguiçoso caso algum estúdio antigo ainda não tenha template piercing
    if "piercing" in tenant.enabled_modules:
        repo = AnamnesisTemplateRepository(session, tenant.studio_id)
        if await repo.get_active_for_module("piercing") is None:
            await ensure_default_piercing_template(
                session, tenant.studio_id, actor_user_id=tenant.user_id
            )
            await session.commit()

    repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    return list(await repo.list_by_module(module=module))


async def create_new_template_version(
    session: AsyncSession,
    tenant: TenantContext,
    payload: AnamnesisTemplateUpsertRequest,
    *,
    request: Request | None = None,
) -> AnamnesisTemplate:
    module_clean = payload.module.strip().lower()
    if module_clean not in tenant.enabled_modules:
        raise ForbiddenError(
            detail=f"O módulo '{module_clean}' não está habilitado para este estúdio.",
            code="MODULE_DISABLED",
        )

    repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    next_ver = (await repo.get_max_version(module_clean)) + 1

    # Desativa versões anteriores do mesmo módulo
    await session.execute(
        sa.update(AnamnesisTemplate)
        .where(
            AnamnesisTemplate.studio_id == tenant.studio_id,
            AnamnesisTemplate.module == module_clean,
            AnamnesisTemplate.is_active.is_(True),
        )
        .values(is_active=False, updated_at=utcnow(), updated_by=tenant.user_id)
    )

    new_tpl = AnamnesisTemplate(
        studio_id=tenant.studio_id,
        module=module_clean,
        version=next_ver,
        title=payload.title.strip(),
        fields_schema=[f.model_dump() for f in payload.fields_schema],
        consent_text=payload.consent_text.strip(),
        is_active=True,
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )
    await repo.add(new_tpl)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="anamnesis_templates",
        entity_id=new_tpl.id,
        action=AuditAction.CREATE,
        metadata_diff={"module": module_clean, "version": next_ver},
        request=request,
    )
    await session.commit()
    await session.refresh(new_tpl)
    return new_tpl


async def update_template_versioned(
    session: AsyncSession,
    tenant: TenantContext,
    template_id: uuid.UUID,
    payload: AnamnesisTemplateUpsertRequest,
    *,
    request: Request | None = None,
) -> AnamnesisTemplate:
    """
    Se o template já estiver vinculado a fichas de anamnese, cria automaticamente
    uma NOVA versão ativa sem sobrescrever o template histórico das fichas antigas.
    """
    repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    existing = await repo.get_by_id_or_404(
        template_id, detail="Modelo de anamnese não encontrado."
    )

    if await repo.is_used_by_records(existing.id):
        return await create_new_template_version(
            session,
            tenant,
            AnamnesisTemplateUpsertRequest(
                module=existing.module,
                title=payload.title,
                fields_schema=payload.fields_schema,
                consent_text=payload.consent_text,
            ),
            request=request,
        )

    updated = await repo.update_by_id(
        existing.id,
        {
            "title": payload.title.strip(),
            "fields_schema": [f.model_dump() for f in payload.fields_schema],
            "consent_text": payload.consent_text.strip(),
            "updated_by": tenant.user_id,
        },
    )
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="anamnesis_templates",
        entity_id=existing.id,
        action=AuditAction.UPDATE,
        metadata_diff={"version": existing.version, "in_place": True},
        request=request,
    )
    await session.commit()
    await session.refresh(updated)
    return updated


async def create_internal_anamnesis_record(
    session: AsyncSession,
    tenant: TenantContext,
    payload: AnamnesisRecordCreateRequest,
    *,
    request: Request,
) -> AnamnesisRecordDetailResponse:
    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id_or_404(
        payload.client_id, detail="Cliente não encontrado."
    )
    _, is_minor = calculate_age_in_timezone(client.birth_date, tenant.timezone)

    if payload.appointment_id is not None:
        appt_repo = AppointmentRepository(session, tenant.studio_id)
        appt = await appt_repo.get_by_id_or_404(
            payload.appointment_id, detail="Agendamento não encontrado."
        )
        if appt.client_id != client.id:
            raise DomainValidationError(
                detail="O agendamento informado não pertence ao cliente selecionado.",
                code="APPOINTMENT_CLIENT_MISMATCH",
            )
        if (
            tenant.role == StudioRole.PROFESSIONAL
            and appt.professional_id != tenant.user_id
        ):
            raise ForbiddenError(
                detail="Profissionais só podem vincular fichas aos próprios agendamentos.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )

    tpl_repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    if payload.template_id is not None:
        template = await tpl_repo.get_by_id_or_404(
            payload.template_id, detail="Modelo de anamnese não encontrado."
        )
    else:
        module_clean = payload.module.strip().lower()
        template = await tpl_repo.get_active_for_module(module_clean)
        if template is None and module_clean == "piercing":
            template = await ensure_default_piercing_template(
                session, tenant.studio_id, actor_user_id=tenant.user_id
            )
        if template is None:
            raise NotFoundError(
                detail="Nenhum modelo ativo de anamnese encontrado para este módulo."
            )

    _validate_answers_against_schema(template.fields_schema, payload.answers)
    cleaned_guardian = _validate_consent_and_minor_signature(
        is_minor=is_minor,
        client=client,
        consent_accepted=payload.consent_accepted,
        guardian_signed_name=payload.guardian_signed_name,
        signature_payload=payload.signature_payload,
    )

    now = utcnow()
    rec_repo = AnamnesisRecordRepository(session, tenant.studio_id)
    record = AnamnesisRecord(
        studio_id=tenant.studio_id,
        client_id=client.id,
        appointment_id=payload.appointment_id,
        template_id=template.id,
        template_version=template.version,
        module=template.module,
        answers=payload.answers,
        guardian_signed_name=cleaned_guardian,
        consent_accepted=True,
        consent_accepted_at=now,
        consent_ip=get_client_ip(request),
        consent_user_agent=(request.headers.get("user-agent", "")[:512] or None),
        signature_payload=payload.signature_payload.strip(),
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )
    await rec_repo.add(record)

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="anamnesis_records",
        entity_id=record.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "client_id": str(client.id),
            "template_version": template.version,
            "is_minor": is_minor,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(record)

    return AnamnesisRecordDetailResponse(
        id=record.id,
        studio_id=record.studio_id,
        client_id=record.client_id,
        client_name=client.full_name,
        appointment_id=record.appointment_id,
        template_id=record.template_id,
        template_version=record.template_version,
        template_title=template.title,
        fields_schema=list(template.fields_schema),
        consent_text=template.consent_text,
        module=record.module,
        answers=record.answers,
        guardian_signed_name=record.guardian_signed_name,
        consent_accepted=record.consent_accepted,
        consent_accepted_at=record.consent_accepted_at,
        consent_ip=record.consent_ip,
        consent_user_agent=record.consent_user_agent,
        signature_payload=record.signature_payload,
        created_by=record.created_by,
        created_at=record.created_at,
    )


async def list_anamnesis_records(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    client_id: uuid.UUID | None = None,
    appointment_id: uuid.UUID | None = None,
) -> list[AnamnesisRecordSummaryResponse]:
    rec_repo = AnamnesisRecordRepository(session, tenant.studio_id)
    rows = list(
        await rec_repo.list_filtered(client_id=client_id, appointment_id=appointment_id)
    )
    if not rows:
        return []

    client_ids = {r.client_id for r in rows}
    clients = (
        await session.execute(
            sa.select(Client).where(
                Client.studio_id == tenant.studio_id,
                Client.id.in_(client_ids),
            )
        )
    ).scalars().all()
    client_map = {c.id: c.full_name for c in clients}

    return [
        AnamnesisRecordSummaryResponse(
            id=r.id,
            studio_id=r.studio_id,
            client_id=r.client_id,
            client_name=client_map.get(r.client_id, "Cliente"),
            appointment_id=r.appointment_id,
            template_id=r.template_id,
            template_version=r.template_version,
            module=r.module,
            guardian_signed_name=r.guardian_signed_name,
            consent_accepted=r.consent_accepted,
            consent_accepted_at=r.consent_accepted_at,
            created_by=r.created_by,
            created_at=r.created_at,
        )
        for r in rows
    ]


async def get_anamnesis_record_detail_audited(
    session: AsyncSession,
    tenant: TenantContext,
    record_id: uuid.UUID,
    *,
    request: Request,
) -> AnamnesisRecordDetailResponse:
    rec_repo = AnamnesisRecordRepository(session, tenant.studio_id)
    record = await rec_repo.get_by_id_or_404(
        record_id, detail="Ficha de anamnese não encontrada."
    )

    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id(record.client_id, include_deleted=True)

    tpl_repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    template = await tpl_repo.get_by_id_or_404(record.template_id)

    # Auditoria obrigatória LGPD de leitura de dados sensíveis de saúde
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="anamnesis_records",
        entity_id=record.id,
        action=AuditAction.READ_SENSITIVE,
        metadata_diff={"client_id": str(record.client_id)},
        request=request,
    )
    await session.commit()

    return AnamnesisRecordDetailResponse(
        id=record.id,
        studio_id=record.studio_id,
        client_id=record.client_id,
        client_name=client.full_name if client else "Cliente",
        appointment_id=record.appointment_id,
        template_id=record.template_id,
        template_version=record.template_version,
        template_title=template.title,
        fields_schema=list(template.fields_schema),
        consent_text=template.consent_text,
        module=record.module,
        answers=record.answers,
        guardian_signed_name=record.guardian_signed_name,
        consent_accepted=record.consent_accepted,
        consent_accepted_at=record.consent_accepted_at,
        consent_ip=record.consent_ip,
        consent_user_agent=record.consent_user_agent,
        signature_payload=record.signature_payload,
        created_by=record.created_by,
        created_at=record.created_at,
    )


async def reject_immutable_anamnesis_mutation(
    session: AsyncSession,
    tenant: TenantContext,
    record_id: uuid.UUID,
) -> None:
    """Verifica 404 multi-tenant primeiro; se pertencer ao estúdio e estiver assinada, retorna 409."""
    rec_repo = AnamnesisRecordRepository(session, tenant.studio_id)
    record = await rec_repo.get_by_id_or_404(
        record_id, detail="Ficha de anamnese não encontrada."
    )
    if record.consent_accepted:
        raise ConflictError(
            detail="Fichas de anamnese assinadas são estritamente imutáveis (LGPD e rastreabilidade clínica).",
            code="ANAMNESIS_IMMUTABLE",
        )
    raise ConflictError(
        detail="Operação de alteração/exclusão não permitida para fichas de anamnese.",
        code="ANAMNESIS_IMMUTABLE",
    )


async def create_public_anamnesis_link(
    session: AsyncSession,
    tenant: TenantContext,
    payload: CreatePublicAnamnesisLinkRequest,
    *,
    request: Request,
) -> PublicAnamnesisLinkCreatedResponse:
    client_repo = ClientRepository(session, tenant.studio_id)
    client = await client_repo.get_by_id_or_404(
        payload.client_id, detail="Cliente não encontrado."
    )
    # Garante que se for menor de idade já possua responsável cadastrado antes de enviar o link
    _, is_minor = calculate_age_in_timezone(client.birth_date, tenant.timezone)
    if is_minor and (
        not client.guardian_name
        or not client.guardian_cpf
        or not client.guardian_whatsapp
    ):
        raise DomainValidationError(
            detail="Cadastre nome, CPF e WhatsApp do responsável legal antes de gerar o link de anamnese do menor.",
            code="MINOR_GUARDIAN_REQUIRED",
        )

    if payload.appointment_id is not None:
        appt_repo = AppointmentRepository(session, tenant.studio_id)
        appt = await appt_repo.get_by_id_or_404(
            payload.appointment_id, detail="Agendamento não encontrado."
        )
        if appt.client_id != client.id:
            raise DomainValidationError(
                detail="Agendamento não pertence ao cliente selecionado.",
                code="APPOINTMENT_CLIENT_MISMATCH",
            )
        if (
            tenant.role == StudioRole.PROFESSIONAL
            and appt.professional_id != tenant.user_id
        ):
            raise ForbiddenError(
                detail="Profissionais só podem gerar links para os próprios agendamentos.",
                code="PROFESSIONAL_OWN_SCHEDULE_ONLY",
            )

    tpl_repo = AnamnesisTemplateRepository(session, tenant.studio_id)
    if payload.template_id is not None:
        template = await tpl_repo.get_by_id_or_404(
            payload.template_id, detail="Modelo de anamnese não encontrado."
        )
    else:
        module_clean = payload.module.strip().lower()
        template = await tpl_repo.get_active_for_module(module_clean)
        if template is None and module_clean == "piercing":
            template = await ensure_default_piercing_template(
                session, tenant.studio_id, actor_user_id=tenant.user_id
            )
        if template is None:
            raise NotFoundError(
                detail="Nenhum modelo ativo de anamnese encontrado para este módulo."
            )

    raw_token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(hours=payload.expires_in_hours)

    link_repo = AnamnesisPublicLinkRepository(session, tenant.studio_id)
    link = AnamnesisPublicLink(
        studio_id=tenant.studio_id,
        client_id=client.id,
        appointment_id=payload.appointment_id,
        template_id=template.id,
        token_hash=_hash_public_token(raw_token),
        expires_at=expires_at,
        created_by=tenant.user_id,
    )
    await link_repo.add(link)

    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="anamnesis_public_links",
        entity_id=link.id,
        action=AuditAction.CREATE,
        metadata_diff={
            "client_id": str(client.id),
            "expires_at": expires_at.isoformat(),
        },
        request=request,
    )
    await session.commit()

    return PublicAnamnesisLinkCreatedResponse(
        link_id=link.id,
        raw_token=raw_token,
        public_path=f"/anamnese/{raw_token}",
        expires_at=expires_at,
        client_id=client.id,
        client_name=client.full_name,
        client_whatsapp=client.whatsapp,
    )


async def get_public_anamnesis_form(
    session: AsyncSession, raw_token: str
) -> PublicAnamnesisFormView:
    token_hash = _hash_public_token(raw_token)
    with bypass_tenant_filter():
        link = (
            await session.execute(
                sa.select(AnamnesisPublicLink).where(
                    AnamnesisPublicLink.token_hash == token_hash
                )
            )
        ).scalar_one_or_none()
        if link is None:
            raise NotFoundError(
                detail="Link de anamnese inválido ou não encontrado.",
                code="LINK_NOT_FOUND",
            )

        studio = (
            await session.execute(
                sa.select(Studio).where(Studio.id == link.studio_id)
            )
        ).scalar_one_or_none()
        if studio is None:
            raise NotFoundError(detail="Estúdio não encontrado.")
        assert_studio_operational(
            is_active=studio.is_active,
            subscription_status=studio.subscription_status,
        )

        if link.used_at is not None or _ensure_utc(link.expires_at) <= utcnow():
            raise GoneError()

        client = (
            await session.execute(
                sa.select(Client).where(
                    Client.id == link.client_id,
                    Client.studio_id == link.studio_id,
                    Client.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if client is None:
            raise GoneError(detail="Cadastro do cliente não está mais ativo.")

        template = (
            await session.execute(
                sa.select(AnamnesisTemplate).where(
                    AnamnesisTemplate.id == link.template_id,
                    AnamnesisTemplate.studio_id == link.studio_id,
                )
            )
        ).scalar_one_or_none()
        if template is None:
            raise NotFoundError(detail="Modelo de formulário não encontrado.")

    _, is_minor = calculate_age_in_timezone(client.birth_date, studio.timezone)
    first_name = client.full_name.strip().split()[0]

    return PublicAnamnesisFormView(
        studio_name=studio.name,
        client_first_name=first_name,
        is_minor=is_minor,
        module=template.module,
        template_title=template.title,
        template_version=template.version,
        fields_schema=list(template.fields_schema),
        consent_text=template.consent_text,
        expires_at=_ensure_utc(link.expires_at),
    )


async def submit_public_anamnesis_form(
    session: AsyncSession,
    raw_token: str,
    payload: PublicAnamnesisSubmitRequest,
    *,
    request: Request,
) -> PublicAnamnesisSubmittedResponse:
    token_hash = _hash_public_token(raw_token)
    now = utcnow()

    with bypass_tenant_filter():
        link = (
            await session.execute(
                sa.select(AnamnesisPublicLink)
                .where(AnamnesisPublicLink.token_hash == token_hash)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if link is None:
            raise NotFoundError(
                detail="Link de anamnese inválido ou não encontrado.",
                code="LINK_NOT_FOUND",
            )

        studio = (
            await session.execute(
                sa.select(Studio).where(Studio.id == link.studio_id)
            )
        ).scalar_one_or_none()
        if studio is None:
            raise NotFoundError(detail="Estúdio não encontrado.")
        assert_studio_operational(
            is_active=studio.is_active,
            subscription_status=studio.subscription_status,
        )

        if link.used_at is not None or _ensure_utc(link.expires_at) <= now:
            raise GoneError()

        client = (
            await session.execute(
                sa.select(Client).where(
                    Client.id == link.client_id,
                    Client.studio_id == link.studio_id,
                    Client.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if client is None:
            raise GoneError(detail="Cadastro do cliente não está mais ativo.")

        template = (
            await session.execute(
                sa.select(AnamnesisTemplate).where(
                    AnamnesisTemplate.id == link.template_id,
                    AnamnesisTemplate.studio_id == link.studio_id,
                )
            )
        ).scalar_one_or_none()
        if template is None:
            raise NotFoundError(detail="Modelo de formulário não encontrado.")

        _, is_minor = calculate_age_in_timezone(client.birth_date, studio.timezone)
        _validate_answers_against_schema(template.fields_schema, payload.answers)
        cleaned_guardian = _validate_consent_and_minor_signature(
            is_minor=is_minor,
            client=client,
            consent_accepted=payload.consent_accepted,
            guardian_signed_name=payload.guardian_signed_name,
            signature_payload=payload.signature_payload,
        )

        record = AnamnesisRecord(
            studio_id=link.studio_id,
            client_id=client.id,
            appointment_id=link.appointment_id,
            template_id=template.id,
            template_version=template.version,
            module=template.module,
            answers=payload.answers,
            guardian_signed_name=cleaned_guardian,
            consent_accepted=True,
            consent_accepted_at=now,
            consent_ip=get_client_ip(request),
            consent_user_agent=(request.headers.get("user-agent", "")[:512] or None),
            signature_payload=payload.signature_payload.strip(),
            created_by=None,
            updated_by=None,
        )
        session.add(record)
        await session.flush()

        link.used_at = now
        link.resulting_record_id = record.id

        await record_audit_log(
            session,
            studio_id=link.studio_id,
            actor_user_id=None,
            entity_name="anamnesis_records",
            entity_id=record.id,
            action=AuditAction.CREATE,
            metadata_diff={
                "source": "public_self_service_link",
                "link_id": str(link.id),
                "client_id": str(client.id),
                "is_minor": is_minor,
            },
            request=request,
        )
        await session.commit()

    return PublicAnamnesisSubmittedResponse(
        record_id=record.id,
        consent_accepted_at=now,
        message="Ficha de anamnese e termo de consentimento registrados com sucesso!",
    )
