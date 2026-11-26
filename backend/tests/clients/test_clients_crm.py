from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.enums import AuditAction
from app.core.timezone import today_in_studio_timezone


async def _bootstrap_two_studios_and_roles(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Aurora Piercing Studio A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Amanda Owner A",
            "owner_email": "amanda@aurora-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Boreal Piercing Studio B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Breno Owner B",
            "owner_email": "breno@boreal-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    owner_a_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "amanda@aurora-a.com", "password": "PasswordA!123"},
    )
    owner_a_token = owner_a_login.json()["access_token"]

    await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Rita Recepção",
            "email": "rita@aurora-a.com",
            "password": "PasswordRita!123",
            "role": "RECEPTION",
        },
    )
    await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Pedro Piercer",
            "email": "pedro@aurora-a.com",
            "password": "PasswordPedro!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "45.00",
            "commission_product_pct": "12.00",
        },
    )

    client.cookies.clear()
    rec_a_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rita@aurora-a.com", "password": "PasswordRita!123"},
    )
    rec_a_token = rec_a_login.json()["access_token"]

    client.cookies.clear()
    prof_a_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pedro@aurora-a.com", "password": "PasswordPedro!123"},
    )
    prof_a_token = prof_a_login.json()["access_token"]

    client.cookies.clear()
    owner_b_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "breno@boreal-b.com", "password": "PasswordB!123"},
    )
    owner_b_token = owner_b_login.json()["access_token"]

    return {
        "owner_a": owner_a_token,
        "reception_a": rec_a_token,
        "professional_a": prof_a_token,
        "owner_b": owner_b_token,
    }


@pytest.mark.asyncio
async def test_client_minor_guardian_enforcement_and_search(
    client: AsyncClient,
) -> None:
    tokens = await _bootstrap_two_studios_and_roles(client)
    rec_headers = {"Authorization": f"Bearer {tokens['reception_a']}"}

    today_sp = today_in_studio_timezone("America/Sao_Paulo")
    minor_birth_date = date(today_sp.year - 16, today_sp.month, today_sp.day)
    adult_birth_date = date(today_sp.year - 25, today_sp.month, today_sp.day)

    # 1. Menor de 18 anos SEM responsável legal -> bloqueado com MINOR_GUARDIAN_REQUIRED
    blocked_minor = await client.post(
        "/api/v1/clients",
        headers=rec_headers,
        json={
            "full_name": "Júlia Menor",
            "whatsapp": "(11) 98888-1122",
            "birth_date": minor_birth_date.isoformat(),
            "lead_source": "INSTAGRAM",
            "tags": ["VIP", "Orelha"],
        },
    )
    assert blocked_minor.status_code == 422
    assert blocked_minor.json()["code"] == "MINOR_GUARDIAN_REQUIRED"

    # 2. Menor de 18 anos COM responsável legal completo -> sucesso
    valid_minor = await client.post(
        "/api/v1/clients",
        headers=rec_headers,
        json={
            "full_name": "Júlia Menor",
            "whatsapp": "(11) 98888-1122",
            "birth_date": minor_birth_date.isoformat(),
            "lead_source": "INSTAGRAM",
            "tags": ["Orelha", "Primeira Perfuração"],
            "guardian_name": "Cláudia Mãe",
            "guardian_cpf": "123.456.789-01",
            "guardian_whatsapp": "(11) 97777-3344",
            "guardian_relationship": "Mãe",
        },
    )
    assert valid_minor.status_code == 201
    minor_data = valid_minor.json()
    assert minor_data["whatsapp"] == "11988881122"
    assert minor_data["is_minor"] is True
    assert minor_data["age"] == 16
    assert minor_data["guardian_cpf"] == "12345678901"

    # 3. Adulto (>= 18) sem responsável -> sucesso
    adult_res = await client.post(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {tokens['professional_a']}"},
        json={
            "full_name": "Marcos Adulto",
            "whatsapp": "+55 11 96666-5544",
            "birth_date": adult_birth_date.isoformat(),
            "lead_source": "INDICACAO",
            "tags": ["Septo"],
        },
    )
    assert adult_res.status_code == 201
    adult_id = adult_res.json()["id"]
    assert adult_res.json()["is_minor"] is False
    assert adult_res.json()["age"] == 25

    # 4. Se tentar alterar data de nascimento de adulto para menor sem responsável -> bloqueia
    invalid_patch = await client.patch(
        f"/api/v1/clients/{adult_id}",
        headers=rec_headers,
        json={"birth_date": (today_sp - timedelta(days=365 * 15)).isoformat()},
    )
    assert invalid_patch.status_code == 422
    assert invalid_patch.json()["code"] == "MINOR_GUARDIAN_REQUIRED"

    # 5. Busca rápida por WhatsApp formatado e filtro only_minors / tag
    search_by_phone = await client.get(
        "/api/v1/clients",
        headers=rec_headers,
        params={"q": "(11) 98888"},
    )
    assert search_by_phone.status_code == 200
    assert len(search_by_phone.json()) == 1
    assert search_by_phone.json()[0]["full_name"] == "Júlia Menor"

    minors_only = await client.get(
        "/api/v1/clients",
        headers=rec_headers,
        params={"only_minors": "true"},
    )
    assert len(minors_only.json()) == 1
    assert minors_only.json()[0]["is_minor"] is True


@pytest.mark.asyncio
async def test_client_whatsapp_partial_unique_soft_delete_audit_and_anti_idor(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tokens = await _bootstrap_two_studios_and_roles(client)
    owner_a_headers = {"Authorization": f"Bearer {tokens['owner_a']}"}
    rec_a_headers = {"Authorization": f"Bearer {tokens['reception_a']}"}
    prof_a_headers = {"Authorization": f"Bearer {tokens['professional_a']}"}
    owner_b_headers = {"Authorization": f"Bearer {tokens['owner_b']}"}

    c1 = await client.post(
        "/api/v1/clients",
        headers=owner_a_headers,
        json={
            "full_name": "Cliente Único",
            "whatsapp": "(21) 99999-0000",
            "birth_date": "1995-05-10",
            "lead_source": "GOOGLE",
        },
    )
    assert c1.status_code == 201
    client_a_id = c1.json()["id"]

    # Duplicidade ativa no mesmo estúdio -> 409
    dup_same_studio = await client.post(
        "/api/v1/clients",
        headers=owner_a_headers,
        json={
            "full_name": "Outro Nome Mesmo Zap",
            "whatsapp": "21999990000",
            "birth_date": "1992-03-15",
        },
    )
    assert dup_same_studio.status_code == 409
    assert dup_same_studio.json()["code"] == "CLIENT_WHATSAPP_ALREADY_EXISTS"

    # Mesmo WhatsApp em OUTRO estúdio (Studio B) -> permitido (isolamento multi-tenant)
    same_phone_studio_b = await client.post(
        "/api/v1/clients",
        headers=owner_b_headers,
        json={
            "full_name": "Cliente Studio B",
            "whatsapp": "(21) 99999-0000",
            "birth_date": "1995-05-10",
        },
    )
    assert same_phone_studio_b.status_code == 201
    client_b_id = same_phone_studio_b.json()["id"]

    # Anti-IDOR: Studio A tentando ler, editar ou deletar cliente do Studio B -> 404
    assert (
        await client.get(f"/api/v1/clients/{client_b_id}", headers=owner_a_headers)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/clients/{client_b_id}",
            headers=owner_a_headers,
            json={"full_name": "Hack"},
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/clients/{client_b_id}", headers=owner_a_headers)
    ).status_code == 404

    # PROFESSIONAL não pode excluir clientes -> 403
    prof_del = await client.delete(
        f"/api/v1/clients/{client_a_id}", headers=prof_a_headers
    )
    assert prof_del.status_code == 403

    # RECEPTION executa soft delete -> 204 + audit_log gravado + libera reuso do WhatsApp no Studio A
    rec_del = await client.delete(
        f"/api/v1/clients/{client_a_id}", headers=rec_a_headers
    )
    assert rec_del.status_code == 204

    audit_row = (
        await db_session.execute(
            sa.select(AuditLog).where(
                AuditLog.entity_name == "clients",
                AuditLog.entity_id == client_a_id,
                AuditLog.action == AuditAction.SOFT_DELETE,
            )
        )
    ).scalar_one_or_none()
    assert audit_row is not None

    recreate_after_soft_delete = await client.post(
        "/api/v1/clients",
        headers=owner_a_headers,
        json={
            "full_name": "Cliente Reativado Novo",
            "whatsapp": "(21) 99999-0000",
            "birth_date": "1995-05-10",
        },
    )
    assert recreate_after_soft_delete.status_code == 201
