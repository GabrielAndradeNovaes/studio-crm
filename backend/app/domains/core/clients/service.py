from __future__ import annotations

import uuid
from datetime import date

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_log
from app.core.enums import AuditAction, LeadSource
from app.core.exceptions import ConflictError, DomainValidationError
from app.core.rbac import TenantContext
from app.core.timezone import calculate_age_in_timezone
from app.domains.core.clients.models import Client
from app.domains.core.clients.repository import ClientRepository
from app.domains.core.clients.schemas import (
    ClientCreateRequest,
    ClientResponse,
    ClientUpdateRequest,
)


def _enforce_minor_guardian_rules(
    *,
    birth_date: date,
    studio_timezone: str,
    guardian_name: str | None,
    guardian_cpf: str | None,
    guardian_whatsapp: str | None,
) -> tuple[int, bool]:
    age, is_minor = calculate_age_in_timezone(birth_date, studio_timezone)
    if is_minor:
        missing: list[str] = []
        if not guardian_name or len(guardian_name.strip()) < 2:
            missing.append("nome do responsável")
        if not guardian_cpf:
            missing.append("CPF do responsável")
        if not guardian_whatsapp:
            missing.append("WhatsApp do responsável")
        if missing:
            raise DomainValidationError(
                detail=(
                    "Cliente menor de 18 anos: informe obrigatoriamente "
                    + ", ".join(missing)
                    + "."
                ),
                code="MINOR_GUARDIAN_REQUIRED",
            )
    return age, is_minor


def _to_client_response(client: Client, *, studio_timezone: str) -> ClientResponse:
    age, is_minor = calculate_age_in_timezone(client.birth_date, studio_timezone)
    return ClientResponse(
        id=client.id,
        studio_id=client.studio_id,
        full_name=client.full_name,
        whatsapp=client.whatsapp,
        email=client.email,
        birth_date=client.birth_date,
        age=age,
        is_minor=is_minor,
        cpf=client.cpf,
        lead_source=client.lead_source,
        tags=list(client.tags or []),
        notes=client.notes,
        guardian_name=client.guardian_name,
        guardian_cpf=client.guardian_cpf,
        guardian_whatsapp=client.guardian_whatsapp,
        guardian_relationship=client.guardian_relationship,
        created_by=client.created_by,
        updated_by=client.updated_by,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


async def list_clients(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    q: str | None = None,
    lead_source: LeadSource | None = None,
    tag: str | None = None,
    only_minors: bool = False,
    offset: int = 0,
    limit: int = 100,
) -> list[ClientResponse]:
    repo = ClientRepository(session, tenant.studio_id)
    rows = await repo.search(
        q=q,
        lead_source=lead_source,
        offset=0 if (tag or only_minors) else offset,
        limit=500 if (tag or only_minors) else limit,
    )

    items = [_to_client_response(c, studio_timezone=tenant.timezone) for c in rows]
    if tag and tag.strip():
        needle = tag.strip().lower()
        items = [
            item
            for item in items
            if any(t.lower() == needle for t in item.tags)
        ]
    if only_minors:
        items = [item for item in items if item.is_minor]

    if tag or only_minors:
        items = items[offset : offset + limit]
    return items


async def get_client_by_id(
    session: AsyncSession, tenant: TenantContext, client_id: uuid.UUID
) -> ClientResponse:
    repo = ClientRepository(session, tenant.studio_id)
    client = await repo.get_by_id_or_404(client_id, detail="Cliente não encontrado.")
    return _to_client_response(client, studio_timezone=tenant.timezone)


async def create_client(
    session: AsyncSession,
    tenant: TenantContext,
    payload: ClientCreateRequest,
    *,
    request: Request | None = None,
) -> ClientResponse:
    _enforce_minor_guardian_rules(
        birth_date=payload.birth_date,
        studio_timezone=tenant.timezone,
        guardian_name=payload.guardian_name,
        guardian_cpf=payload.guardian_cpf,
        guardian_whatsapp=payload.guardian_whatsapp,
    )

    repo = ClientRepository(session, tenant.studio_id)
    duplicate = await repo.get_active_by_whatsapp(payload.whatsapp)
    if duplicate is not None:
        raise ConflictError(
            detail="Já existe um cliente ativo cadastrado com este WhatsApp neste estúdio.",
            code="CLIENT_WHATSAPP_ALREADY_EXISTS",
        )

    client = Client(
        studio_id=tenant.studio_id,
        full_name=payload.full_name.strip(),
        whatsapp=payload.whatsapp,
        email=payload.email.strip().lower() if payload.email else None,
        birth_date=payload.birth_date,
        cpf=payload.cpf,
        lead_source=payload.lead_source,
        tags=payload.tags,
        notes=payload.notes.strip() if payload.notes else None,
        guardian_name=payload.guardian_name.strip() if payload.guardian_name else None,
        guardian_cpf=payload.guardian_cpf,
        guardian_whatsapp=payload.guardian_whatsapp,
        guardian_relationship=(
            payload.guardian_relationship.strip()
            if payload.guardian_relationship
            else None
        ),
        created_by=tenant.user_id,
        updated_by=tenant.user_id,
    )

    try:
        await repo.add(client)
        await record_audit_log(
            session,
            studio_id=tenant.studio_id,
            actor_user_id=tenant.user_id,
            entity_name="clients",
            entity_id=client.id,
            action=AuditAction.CREATE,
            metadata_diff={"whatsapp": client.whatsapp, "lead_source": client.lead_source.value},
            request=request,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            detail="Já existe um cliente ativo cadastrado com este WhatsApp neste estúdio.",
            code="CLIENT_WHATSAPP_ALREADY_EXISTS",
        ) from exc

    await session.refresh(client)
    return _to_client_response(client, studio_timezone=tenant.timezone)


async def update_client(
    session: AsyncSession,
    tenant: TenantContext,
    client_id: uuid.UUID,
    payload: ClientUpdateRequest,
    *,
    request: Request | None = None,
) -> ClientResponse:
    repo = ClientRepository(session, tenant.studio_id)
    existing = await repo.get_by_id_or_404(client_id, detail="Cliente não encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _to_client_response(existing, studio_timezone=tenant.timezone)

    effective_birth_date = changes.get("birth_date", existing.birth_date)
    effective_guardian_name = changes.get("guardian_name", existing.guardian_name)
    effective_guardian_cpf = changes.get("guardian_cpf", existing.guardian_cpf)
    effective_guardian_whatsapp = changes.get(
        "guardian_whatsapp", existing.guardian_whatsapp
    )

    _enforce_minor_guardian_rules(
        birth_date=effective_birth_date,
        studio_timezone=tenant.timezone,
        guardian_name=effective_guardian_name,
        guardian_cpf=effective_guardian_cpf,
        guardian_whatsapp=effective_guardian_whatsapp,
    )

    if "whatsapp" in changes and changes["whatsapp"] != existing.whatsapp:
        dup = await repo.get_active_by_whatsapp(
            changes["whatsapp"], exclude_client_id=client_id
        )
        if dup is not None:
            raise ConflictError(
                detail="Já existe outro cliente ativo com este WhatsApp neste estúdio.",
                code="CLIENT_WHATSAPP_ALREADY_EXISTS",
            )

    if "full_name" in changes and changes["full_name"]:
        changes["full_name"] = changes["full_name"].strip()
    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].strip().lower()
    if "guardian_name" in changes and changes["guardian_name"]:
        changes["guardian_name"] = changes["guardian_name"].strip()
    changes["updated_by"] = tenant.user_id

    try:
        updated = await repo.update_by_id(client_id, changes)
        await record_audit_log(
            session,
            studio_id=tenant.studio_id,
            actor_user_id=tenant.user_id,
            entity_name="clients",
            entity_id=client_id,
            action=AuditAction.UPDATE,
            metadata_diff={
                k: (v.value if hasattr(v, "value") else str(v))
                for k, v in changes.items()
                if k != "updated_by"
            },
            request=request,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            detail="Já existe outro cliente ativo com este WhatsApp neste estúdio.",
            code="CLIENT_WHATSAPP_ALREADY_EXISTS",
        ) from exc

    await session.refresh(updated)
    return _to_client_response(updated, studio_timezone=tenant.timezone)


async def soft_delete_client(
    session: AsyncSession,
    tenant: TenantContext,
    client_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    repo = ClientRepository(session, tenant.studio_id)
    client = await repo.get_by_id_or_404(client_id, detail="Cliente não encontrado.")
    await repo.soft_delete_by_id(client.id, actor_user_id=tenant.user_id)
    await record_audit_log(
        session,
        studio_id=tenant.studio_id,
        actor_user_id=tenant.user_id,
        entity_name="clients",
        entity_id=client.id,
        action=AuditAction.SOFT_DELETE,
        metadata_diff={"full_name": client.full_name, "whatsapp": client.whatsapp},
        request=request,
    )
    await session.commit()
