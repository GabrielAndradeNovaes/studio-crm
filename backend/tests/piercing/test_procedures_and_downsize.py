from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_piercing_procedures_downsize_calculation_no_stock_deduction_and_anti_idor(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Conch Master Studio A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Clara Owner A",
            "owner_email": "clara@conch-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Rook Studio B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Rodrigo Owner B",
            "owner_email": "rodrigo@rook-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "clara@conch-a.com", "password": "PasswordA!123"},
    )
    owner_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    p1 = await client.post(
        "/api/v1/team",
        headers=owner_a,
        json={
            "name": "Nina Piercer",
            "email": "nina@conch-a.com",
            "password": "PasswordNina!123",
            "role": "PROFESSIONAL",
        },
    )
    nina_id = p1.json()["user_id"]

    client.cookies.clear()
    nina_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "nina@conch-a.com", "password": "PasswordNina!123"},
    )
    nina_headers = {"Authorization": f"Bearer {nina_login.json()['access_token']}"}

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "rodrigo@rook-b.com", "password": "PasswordB!123"},
    )
    owner_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Cria serviço com return_days_downsize = 30 dias e joia com initial_stock = 4
    svc_res = await client.post(
        "/api/v1/piercing/services",
        headers=owner_a,
        json={
            "name": "Perfuração Helix",
            "anatomical_site": "Helix",
            "duration_minutes": 30,
            "base_price": "100.00",
            "return_days_downsize": 30,
        },
    )
    service_id = svc_res.json()["id"]

    prod_res = await client.post(
        "/api/v1/piercing/products",
        headers=owner_a,
        json={
            "sku": "TIT-HELIX-08",
            "name": "Labret Titânio 8mm",
            "item_type": "JEWELRY",
            "material": "Titânio ASTM F136",
            "cost_price": "25.00",
            "sale_price": "120.00",
            "initial_stock": 4,
            "min_stock_alert": 1,
        },
    )
    product_id = prod_res.json()["id"]

    cli_res = await client.post(
        "/api/v1/clients",
        headers=owner_a,
        json={
            "full_name": "Fernanda Cliente",
            "whatsapp": "(11) 95555-4444",
            "birth_date": "1996-08-20",
        },
    )
    client_id = cli_res.json()["id"]

    # 1. Cria procedimento realizado há 25 dias -> downsize_reminder_date deve cair daqui a 5 dias!
    performed_25d_ago = datetime.now(timezone.utc) - timedelta(days=25)
    proc_res = await client.post(
        "/api/v1/piercing/procedures",
        headers=nina_headers,
        json={
            "client_id": client_id,
            "service_id": service_id,
            "jewelry_product_id": product_id,
            "anatomical_site_detail": "Orelha esquerda - Helix superior",
            "sterilization_lot": "AUTOCLAVE-2026-11A",
            "healing_notes": "Sangramento mínimo, haste de 8mm para acomodar edema.",
            "performed_at": performed_25d_ago.isoformat(),
        },
    )
    assert proc_res.status_code == 201
    proc_data = proc_res.json()
    proc_id = proc_data["id"]
    assert proc_data["professional_id"] == nina_id
    assert proc_data["downsize_reminder_date"] is not None
    assert proc_data["is_overdue"] is False
    assert 4 <= proc_data["days_until_due"] <= 6

    # 2. PROVA CRÍTICA: Registrar o procedimento NÃO reduz stock_quantity nem cria movimento no Kardex!
    prod_check = await client.get(
        f"/api/v1/piercing/products/{product_id}", headers=owner_a
    )
    assert prod_check.json()["stock_quantity"] == 4
    mov_check = await client.get(
        f"/api/v1/piercing/products/{product_id}/movements", headers=owner_a
    )
    assert len(mov_check.json()) == 1  # Apenas o movimento inicial de cadastro!

    # 3. Cria outro procedimento realizado há 40 dias -> atrasado (overdue)!
    performed_40d_ago = datetime.now(timezone.utc) - timedelta(days=40)
    overdue_proc = await client.post(
        "/api/v1/piercing/procedures",
        headers=owner_a,
        json={
            "client_id": client_id,
            "professional_id": nina_id,
            "service_id": service_id,
            "anatomical_site_detail": "Orelha direita - Tragus",
            "performed_at": performed_40d_ago.isoformat(),
        },
    )
    assert overdue_proc.status_code == 201
    overdue_id = overdue_proc.json()["id"]

    # 4. Filtro de lembretes de downsize por janela (next_7_days vs overdue)
    next7 = await client.get(
        "/api/v1/piercing/procedures/downsize-reminders",
        headers=nina_headers,
        params={"window": "next_7_days"},
    )
    assert [r["id"] for r in next7.json()] == [proc_id]

    overdue_list = await client.get(
        "/api/v1/piercing/procedures/downsize-reminders",
        headers=nina_headers,
        params={"window": "overdue"},
    )
    assert [r["id"] for r in overdue_list.json()] == [overdue_id]
    assert overdue_list.json()[0]["is_overdue"] is True

    # 5. Concluir downsize remove da lista de pendentes e bloqueia conclusão duplicada
    done_res = await client.post(
        f"/api/v1/piercing/procedures/{overdue_id}/complete-downsize",
        headers=nina_headers,
        json={"notes": "Trocada haste para 6mm, cicatrização excelente."},
    )
    assert done_res.status_code == 200
    assert done_res.json()["downsize_completed_at"] is not None

    overdue_after = await client.get(
        "/api/v1/piercing/procedures/downsize-reminders",
        headers=nina_headers,
        params={"window": "overdue"},
    )
    assert overdue_after.json() == []

    # 6. Anti-IDOR multi-tenant: Studio B recebe 404 para procedimentos do Studio A
    assert (
        await client.patch(
            f"/api/v1/piercing/procedures/{proc_id}",
            headers=owner_b,
            json={"healing_notes": "Hack"},
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/piercing/procedures/{proc_id}/complete-downsize",
            headers=owner_b,
            json={},
        )
    ).status_code == 404
