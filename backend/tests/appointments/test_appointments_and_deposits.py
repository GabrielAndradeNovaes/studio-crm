from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _setup_schedule_context(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Helix Lab Studio A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Helena Owner A",
            "owner_email": "helena@helix-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Septum Lab Studio B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Sérgio Owner B",
            "owner_email": "sergio@septum-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "helena@helix-a.com", "password": "PasswordA!123"},
    )
    owner_a_token = login_a.json()["access_token"]

    rec_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Roberta Recepção",
            "email": "roberta@helix-a.com",
            "password": "PasswordRec!123",
            "role": "RECEPTION",
        },
    )
    assert rec_res.status_code == 201

    p1_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Paula Piercer 1",
            "email": "paula@helix-a.com",
            "password": "PasswordP1!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "50.00",
        },
    )
    prof1_user_id = p1_res.json()["user_id"]

    p2_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Priscila Piercer 2",
            "email": "priscila@helix-a.com",
            "password": "PasswordP2!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "45.00",
        },
    )
    prof2_user_id = p2_res.json()["user_id"]

    svc_res = await client.post(
        "/api/v1/piercing/services",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Perfuração Daith",
            "anatomical_site": "Daith",
            "duration_minutes": 45,
            "base_price": "140.00",
            "return_days_downsize": 40,
        },
    )
    service_id = svc_res.json()["id"]

    cli_res = await client.post(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "full_name": "Camila Cliente",
            "whatsapp": "(11) 98888-1000",
            "birth_date": "1998-04-12",
            "lead_source": "INSTAGRAM",
        },
    )
    client_a_id = cli_res.json()["id"]

    client.cookies.clear()
    rec_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "roberta@helix-a.com", "password": "PasswordRec!123"},
    )
    rec_a_token = rec_login.json()["access_token"]

    client.cookies.clear()
    p1_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "paula@helix-a.com", "password": "PasswordP1!123"},
    )
    prof1_token = p1_login.json()["access_token"]

    client.cookies.clear()
    p2_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "priscila@helix-a.com", "password": "PasswordP2!123"},
    )
    prof2_token = p2_login.json()["access_token"]

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "sergio@septum-b.com", "password": "PasswordB!123"},
    )
    owner_b_token = login_b.json()["access_token"]

    return {
        "owner_a": owner_a_token,
        "reception_a": rec_a_token,
        "prof1_token": prof1_token,
        "prof1_id": prof1_user_id,
        "prof2_token": prof2_token,
        "prof2_id": prof2_user_id,
        "service_id": service_id,
        "client_a_id": client_a_id,
        "owner_b": owner_b_token,
    }


@pytest.mark.asyncio
async def test_appointment_overlap_professional_isolation_deposit_and_anti_idor(
    client: AsyncClient,
) -> None:
    ctx = await _setup_schedule_context(client)
    rec_a = {"Authorization": f"Bearer {ctx['reception_a']}"}
    prof1 = {"Authorization": f"Bearer {ctx['prof1_token']}"}
    prof2 = {"Authorization": f"Bearer {ctx['prof2_token']}"}
    owner_b = {"Authorization": f"Bearer {ctx['owner_b']}"}

    base_start = datetime(2026, 11, 28, 14, 0, tzinfo=timezone.utc)

    # 1. Criação de agendamento usa automaticamente duration_minutes=45 do serviço (14:00 -> 14:45)
    appt1_res = await client.post(
        "/api/v1/appointments",
        headers=rec_a,
        json={
            "client_id": ctx["client_a_id"],
            "professional_id": ctx["prof1_id"],
            "service_id": ctx["service_id"],
            "start_at": base_start.isoformat(),
            "notes": "Joia em titânio",
        },
    )
    assert appt1_res.status_code == 201
    appt1_id = appt1_res.json()["id"]

    # 2. Conflito de horário para a MESMA profissional (14:30 -> 15:15 sobrepõe 14:00 -> 14:45) -> 409
    overlap_res = await client.post(
        "/api/v1/appointments",
        headers=rec_a,
        json={
            "client_id": ctx["client_a_id"],
            "professional_id": ctx["prof1_id"],
            "service_id": ctx["service_id"],
            "start_at": (base_start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert overlap_res.status_code == 409
    assert overlap_res.json()["code"] == "APPOINTMENT_TIME_CONFLICT"

    # 3. Mesmo horário para OUTRA profissional do mesmo estúdio (prof2) -> permitido!
    appt2_res = await client.post(
        "/api/v1/appointments",
        headers=rec_a,
        json={
            "client_id": ctx["client_a_id"],
            "professional_id": ctx["prof2_id"],
            "service_id": ctx["service_id"],
            "start_at": base_start.isoformat(),
        },
    )
    assert appt2_res.status_code == 201
    appt2_id = appt2_res.json()["id"]

    # 4. Isolamento RBAC de PROFESSIONAL:
    # Prof1 enxerga apenas o próprio agendamento e recebe 403 ao tentar acessar/editar o de Prof2
    p1_list = await client.get("/api/v1/appointments", headers=prof1)
    assert p1_list.status_code == 200
    assert [a["id"] for a in p1_list.json()] == [appt1_id]

    assert (
        await client.get(
            "/api/v1/appointments",
            headers=prof1,
            params={"professional_id": ctx["prof2_id"]},
        )
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/appointments/{appt2_id}", headers=prof1)
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/appointments/{appt2_id}",
            headers=prof1,
            json={"status": "EM_ATENDIMENTO"},
        )
    ).status_code == 403

    # Prof1 atualiza status do PRÓPRIO agendamento com sucesso
    own_patch = await client.patch(
        f"/api/v1/appointments/{appt1_id}",
        headers=prof1,
        json={"status": "CONFIRMADO", "notes": "Confirmado com a cliente"},
    )
    assert own_patch.status_code == 200
    assert own_patch.json()["status"] == "CONFIRMADO"

    # 5. Registro de sinal sem duplicidade (RECEPTION/OWNER)
    dep_res = await client.post(
        f"/api/v1/appointments/{appt1_id}/deposit",
        headers=rec_a,
        json={"amount": "50.00", "payment_method": "PIX"},
    )
    assert dep_res.status_code == 200
    assert Decimal(dep_res.json()["deposit_amount"]) == Decimal("50.00")
    assert dep_res.json()["deposit_status"] == "PAID"
    assert dep_res.json()["deposit_payment_method"] == "PIX"

    dup_dep = await client.post(
        f"/api/v1/appointments/{appt1_id}/deposit",
        headers=rec_a,
        json={"amount": "50.00", "payment_method": "PIX"},
    )
    assert dup_dep.status_code == 409
    assert dup_dep.json()["code"] == "DEPOSIT_ALREADY_PAID"

    # 6. Se appt2 for CANCELADO, libera o horário de prof2 para novo agendamento!
    await client.patch(
        f"/api/v1/appointments/{appt2_id}",
        headers=rec_a,
        json={"status": "CANCELADO"},
    )
    rebook_prof2 = await client.post(
        "/api/v1/appointments",
        headers=rec_a,
        json={
            "client_id": ctx["client_a_id"],
            "professional_id": ctx["prof2_id"],
            "service_id": ctx["service_id"],
            "start_at": base_start.isoformat(),
        },
    )
    assert rebook_prof2.status_code == 201

    # 7. Anti-IDOR multi-tenant: Studio B recebe 404 para agendamento do Studio A
    assert (
        await client.get(f"/api/v1/appointments/{appt1_id}", headers=owner_b)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/appointments/{appt1_id}/deposit",
            headers=owner_b,
            json={"amount": "20.00", "payment_method": "PIX"},
        )
    ).status_code == 404
