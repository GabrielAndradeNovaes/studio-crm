from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.enums import AuditAction
from app.core.timezone import today_in_studio_timezone, utcnow
from app.domains.core.anamnesis.models import AnamnesisPublicLink, AnamnesisRecord


def _valid_piercing_answers() -> dict[str, object]:
    return {
        "allergies": {"value": False, "details": ""},
        "diabetes": False,
        "blood_pressure": False,
        "coagulation_disorders": False,
        "keloid_history": False,
        "medications": "Nenhum",
        "pregnant_or_nursing": False,
        "infectious_diseases": False,
        "fed_recently": True,
        "additional_notes": "Primeira perfuração auricular",
    }


@pytest.mark.asyncio
async def test_anamnesis_versioning_immutability_lgpd_audit_minor_and_public_links(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "BioSafe Piercing A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Bianca Owner A",
            "owner_email": "bianca@biosafe-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Other Studio B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Bruno Owner B",
            "owner_email": "bruno@other-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "bianca@biosafe-a.com", "password": "PasswordA!123"},
    )
    owner_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "bruno@other-b.com", "password": "PasswordB!123"},
    )
    owner_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # 1. Template padrão de Body Piercing em português já nasce criado na versão 1
    tpl_res = await client.get("/api/v1/anamnesis/templates", headers=owner_a)
    assert tpl_res.status_code == 200
    assert len(tpl_res.json()) == 1
    tpl_v1 = tpl_res.json()[0]
    assert tpl_v1["module"] == "piercing"
    assert tpl_v1["version"] == 1
    assert tpl_v1["is_active"] is True

    # Cadastra cliente menor de 18 anos com responsável
    today_sp = today_in_studio_timezone("America/Sao_Paulo")
    minor_dob = date(today_sp.year - 15, today_sp.month, today_sp.day)
    minor_res = await client.post(
        "/api/v1/clients",
        headers=owner_a,
        json={
            "full_name": "Lara Menor",
            "whatsapp": "(11) 97777-2222",
            "cpf": "111.222.333-44",
            "birth_date": minor_dob.isoformat(),
            "guardian_name": "Luciana Mãe",
            "guardian_cpf": "555.666.777-88",
            "guardian_whatsapp": "(11) 96666-1111",
        },
    )
    assert minor_res.status_code == 201
    minor_id = minor_res.json()["id"]

    # 2. Trava de menor na anamnese: sem guardian_signed_name -> 422 MINOR_GUARDIAN_SIGNATURE_REQUIRED
    missing_guardian_sig = await client.post(
        "/api/v1/anamnesis/records",
        headers=owner_a,
        json={
            "client_id": minor_id,
            "answers": _valid_piercing_answers(),
            "consent_accepted": True,
            "signature_payload": "Assinatura digital",
        },
    )
    assert missing_guardian_sig.status_code == 422
    assert missing_guardian_sig.json()["code"] == "MINOR_GUARDIAN_SIGNATURE_REQUIRED"

    # 3. Criação válida com assinatura do responsável
    rec_res = await client.post(
        "/api/v1/anamnesis/records",
        headers=owner_a,
        json={
            "client_id": minor_id,
            "answers": _valid_piercing_answers(),
            "guardian_signed_name": "Luciana Mãe",
            "consent_accepted": True,
            "signature_payload": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
        },
    )
    assert rec_res.status_code == 201
    record_id = rec_res.json()["id"]
    assert rec_res.json()["template_version"] == 1

    # 4. Imutabilidade estrita da ficha assinada -> 409 ANAMNESIS_IMMUTABLE em PATCH, PUT e DELETE
    for method in ("PATCH", "PUT", "DELETE"):
        mut_res = await client.request(
            method,
            f"/api/v1/anamnesis/records/{record_id}",
            headers=owner_a,
            json={"answers": {}} if method != "DELETE" else None,
        )
        assert mut_res.status_code == 409
        assert mut_res.json()["code"] == "ANAMNESIS_IMMUTABLE"

    # 5. Leitura de detalhes gera obrigatoriamente audit_log READ_SENSITIVE (LGPD)
    read_res = await client.get(
        f"/api/v1/anamnesis/records/{record_id}", headers=owner_a
    )
    assert read_res.status_code == 200

    audit_read = (
        await db_session.execute(
            sa.select(AuditLog).where(
                AuditLog.entity_name == "anamnesis_records",
                AuditLog.entity_id == record_id,
                AuditLog.action == AuditAction.READ_SENSITIVE,
            )
        )
    ).scalar_one_or_none()
    assert audit_read is not None

    # 6. Editar template já usado em ficha assinada cria NOVA VERSÃO (v2) preservando v1 intacta!
    upd_tpl = await client.put(
        f"/api/v1/anamnesis/templates/{tpl_v1['id']}",
        headers=owner_a,
        json={
            "module": "piercing",
            "title": "Ficha Body Piercing v2 Atualizada",
            "fields_schema": tpl_v1["fields_schema"],
            "consent_text": tpl_v1["consent_text"] + "\nCláusula adicional v2.",
        },
    )
    assert upd_tpl.status_code == 200
    assert upd_tpl.json()["version"] == 2
    assert upd_tpl.json()["id"] != tpl_v1["id"]

    # Ficha antiga continua apontando para v1 sem perder o termo original
    old_rec_check = await client.get(
        f"/api/v1/anamnesis/records/{record_id}", headers=owner_a
    )
    assert old_rec_check.json()["template_version"] == 1
    assert "Cláusula adicional v2" not in old_rec_check.json()["consent_text"]

    # 7. Fluxo completo do Link Público de Autoatendimento (sem auth + uso único + expiração 410)
    link_res = await client.post(
        "/api/v1/anamnesis/public-links",
        headers=owner_a,
        json={"client_id": minor_id, "expires_in_hours": 24},
    )
    assert link_res.status_code == 201
    raw_token = link_res.json()["raw_token"]

    # GET público sem token de login: retorna apenas primeiro nome e flag is_minor (sem CPF/WhatsApp!)
    pub_view = await client.get(f"/api/v1/public/anamnesis/{raw_token}")
    assert pub_view.status_code == 200
    pub_data = pub_view.json()
    assert pub_data["client_first_name"] == "Lara"
    assert pub_data["is_minor"] is True
    assert pub_data["template_version"] == 2
    assert "cpf" not in pub_data
    assert "whatsapp" not in pub_data

    # POST público sem login -> grava created_by = NULL e invalida o link para reuso
    pub_submit = await client.post(
        f"/api/v1/public/anamnesis/{raw_token}",
        json={
            "answers": _valid_piercing_answers(),
            "guardian_signed_name": "Luciana Mãe",
            "consent_accepted": True,
            "signature_payload": "Confirmado digitalmente por Luciana Mãe",
        },
    )
    assert pub_submit.status_code == 200
    pub_record_id = pub_submit.json()["record_id"]

    db_record = (
        await db_session.execute(
            sa.select(AnamnesisRecord).where(
                AnamnesisRecord.id == sa.Uuid().bind_processor(db_session.bind.dialect)(pub_record_id)
                if False
                else AnamnesisRecord.module == "piercing"
            )
        )
    ).scalars().all()
    public_saved = next(r for r in db_record if str(r.id) == pub_record_id)
    assert public_saved.created_by is None
    assert public_saved.consent_ip is not None

    # Tentativa de reutilizar o mesmo link -> 410 LINK_EXPIRED_OR_USED
    reuse_view = await client.get(f"/api/v1/public/anamnesis/{raw_token}")
    assert reuse_view.status_code == 410
    assert reuse_view.json()["code"] == "LINK_EXPIRED_OR_USED"

    reuse_post = await client.post(
        f"/api/v1/public/anamnesis/{raw_token}",
        json={
            "answers": _valid_piercing_answers(),
            "guardian_signed_name": "Luciana Mãe",
            "consent_accepted": True,
            "signature_payload": "Replay",
        },
    )
    assert reuse_post.status_code == 410

    # Link expirado também retorna 410
    link2_res = await client.post(
        "/api/v1/anamnesis/public-links",
        headers=owner_a,
        json={"client_id": minor_id, "expires_in_hours": 1},
    )
    token2 = link2_res.json()["raw_token"]
    await db_session.execute(
        sa.update(AnamnesisPublicLink)
        .where(AnamnesisPublicLink.resulting_record_id.is_(None))
        .values(expires_at=utcnow() - timedelta(minutes=5))
    )
    await db_session.commit()
    expired_res = await client.get(f"/api/v1/public/anamnesis/{token2}")
    assert expired_res.status_code == 410

    # 8. Anti-IDOR multi-tenant: Studio B recebe 404 para templates, fichas e cliente do Studio A
    assert (
        await client.get(f"/api/v1/anamnesis/records/{record_id}", headers=owner_b)
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/anamnesis/templates/{tpl_v1['id']}",
            headers=owner_b,
            json={
                "module": "piercing",
                "title": "Hack",
                "fields_schema": tpl_v1["fields_schema"],
                "consent_text": " Texto longo suficiente para validar schema ",
            },
        )
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/anamnesis/public-links",
            headers=owner_b,
            json={"client_id": minor_id},
        )
    ).status_code == 404
