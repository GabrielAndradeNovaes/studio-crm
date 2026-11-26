from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import ensure_superadmin


async def _setup_piercing_context(
    client: AsyncClient, db_session: AsyncSession
) -> dict[str, str]:
    await ensure_superadmin(
        db_session,
        email="sa@platform.com",
        password="SuperPassword!123",
        name="Platform Admin",
    )
    sa_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "sa@platform.com", "password": "SuperPassword!123"},
    )
    sa_token = sa_login.json()["access_token"]

    client.cookies.clear()
    res_a = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Titanium Studio A",
            "owner_name": "Olivia Owner A",
            "owner_email": "olivia@titanium-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    studio_a_id = res_a.json()["id"]

    res_b = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Obsidian Studio B",
            "owner_name": "Otávio Owner B",
            "owner_email": "otavio@obsidian-b.com",
            "owner_password": "PasswordB!123",
        },
    )
    studio_b_id = res_b.json()["id"]

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "olivia@titanium-a.com", "password": "PasswordA!123"},
    )
    owner_a_token = login_a.json()["access_token"]

    await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Raquel Recepção",
            "email": "raquel@titanium-a.com",
            "password": "PasswordRaquel!123",
            "role": "RECEPTION",
        },
    )
    await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={
            "name": "Pâmela Piercer",
            "email": "pamela@titanium-a.com",
            "password": "PasswordPamela!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "50.00",
            "commission_product_pct": "15.00",
        },
    )

    client.cookies.clear()
    rec_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "raquel@titanium-a.com", "password": "PasswordRaquel!123"},
    )
    rec_a_token = rec_login.json()["access_token"]

    client.cookies.clear()
    prof_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pamela@titanium-a.com", "password": "PasswordPamela!123"},
    )
    prof_a_token = prof_login.json()["access_token"]

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "otavio@obsidian-b.com", "password": "PasswordB!123"},
    )
    owner_b_token = login_b.json()["access_token"]

    return {
        "superadmin": sa_token,
        "studio_a_id": studio_a_id,
        "studio_b_id": studio_b_id,
        "owner_a": owner_a_token,
        "reception_a": rec_a_token,
        "professional_a": prof_a_token,
        "owner_b": owner_b_token,
    }


@pytest.mark.asyncio
async def test_piercing_services_rbac_anti_idor_and_module_guard(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ctx = await _setup_piercing_context(client, db_session)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}
    rec_a = {"Authorization": f"Bearer {ctx['reception_a']}"}
    prof_a = {"Authorization": f"Bearer {ctx['professional_a']}"}
    owner_b = {"Authorization": f"Bearer {ctx['owner_b']}"}
    sa_headers = {"Authorization": f"Bearer {ctx['superadmin']}"}

    # OWNER cria serviço de perfuração
    svc_res = await client.post(
        "/api/v1/piercing/services",
        headers=owner_a,
        json={
            "name": "Perfuração Auricular Conch",
            "anatomical_site": "Conch",
            "duration_minutes": 40,
            "base_price": "110.00",
            "return_days_downsize": 35,
            "aftercare_instructions": "Lavar com soro fisiológico 2x ao dia.",
        },
    )
    assert svc_res.status_code == 201
    svc_id = svc_res.json()["id"]

    # RECEPTION e PROFESSIONAL têm acesso somente leitura
    assert (await client.get("/api/v1/piercing/services", headers=rec_a)).status_code == 200
    assert (await client.get("/api/v1/piercing/services", headers=prof_a)).status_code == 200

    assert (
        await client.post(
            "/api/v1/piercing/services",
            headers=rec_a,
            json={
                "name": "Helix",
                "anatomical_site": "Helix",
                "duration_minutes": 30,
                "base_price": "90.00",
            },
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/piercing/services/{svc_id}",
            headers=prof_a,
            json={"base_price": "50.00"},
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/piercing/services/{svc_id}", headers=rec_a)
    ).status_code == 403

    # Anti-IDOR: Studio B não acessa, edita nem exclui serviço do Studio A -> 404
    assert (
        await client.get(f"/api/v1/piercing/services/{svc_id}", headers=owner_b)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/piercing/services/{svc_id}",
            headers=owner_b,
            json={"name": "Invasão"},
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/piercing/services/{svc_id}", headers=owner_b)
    ).status_code == 404

    # Module Guard: se o estúdio tiver apenas ["tattoo"], rotas /piercing/* retornam 403 MODULE_DISABLED
    await client.patch(
        f"/api/v1/admin/studios/{ctx['studio_b_id']}",
        headers=sa_headers,
        json={"enabled_modules": ["tattoo"]},
    )
    blocked_svc = await client.get("/api/v1/piercing/services", headers=owner_b)
    assert blocked_svc.status_code == 403
    assert blocked_svc.json()["code"] == "MODULE_DISABLED"

    blocked_prod = await client.get("/api/v1/piercing/products", headers=owner_b)
    assert blocked_prod.status_code == 403
    assert blocked_prod.json()["code"] == "MODULE_DISABLED"


@pytest.mark.asyncio
async def test_inventory_kardex_immutability_negative_stock_and_cost_omission(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ctx = await _setup_piercing_context(client, db_session)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}
    rec_a = {"Authorization": f"Bearer {ctx['reception_a']}"}
    prof_a = {"Authorization": f"Bearer {ctx['professional_a']}"}
    owner_b = {"Authorization": f"Bearer {ctx['owner_b']}"}

    # 1. Criação de joia com initial_stock=5 gera movimento inicial no Kardex automaticamente
    prod_res = await client.post(
        "/api/v1/piercing/products",
        headers=owner_a,
        json={
            "sku": "TIT-LAB-12-08",
            "name": "Labret Titânio Topo Zircônia",
            "item_type": "JEWELRY",
            "category_site": "Auricular",
            "material": "Titânio ASTM F136",
            "threading_type": "Rosca Interna",
            "gauge_thickness": "1.2mm",
            "length_diameter": "8mm",
            "cost_price": "28.50",
            "sale_price": "135.00",
            "initial_stock": 5,
            "min_stock_alert": 2,
        },
    )
    assert prod_res.status_code == 201
    prod_data = prod_res.json()
    product_id = prod_data["id"]
    assert prod_data["stock_quantity"] == 5
    assert Decimal(prod_data["cost_price"]) == Decimal("28.50")
    assert prod_data["is_low_stock"] is False

    # Verifica o movimento inicial gerado no Kardex
    mov_initial = await client.get(
        f"/api/v1/piercing/products/{product_id}/movements", headers=owner_a
    )
    assert mov_initial.status_code == 200
    assert len(mov_initial.json()) == 1
    assert mov_initial.json()[0]["movement_type"] == "IN_PURCHASE"
    assert mov_initial.json()[0]["quantity_delta"] == 5
    assert mov_initial.json()[0]["resulting_stock"] == 5
    assert Decimal(mov_initial.json()[0]["unit_cost_snapshot"]) == Decimal("28.50")

    # 2. Bloqueio estrito de alteração direta de stock_quantity no PATCH
    direct_stock_attempt = await client.patch(
        f"/api/v1/piercing/products/{product_id}",
        headers=owner_a,
        json={"stock_quantity": 99},
    )
    assert direct_stock_attempt.status_code == 422
    assert direct_stock_attempt.json()["code"] == "DIRECT_STOCK_EDIT_FORBIDDEN"

    # 3. Entrada de compra (+3 unidades com novo custo unitário R$ 32.00)
    purchase_res = await client.post(
        f"/api/v1/piercing/products/{product_id}/movements",
        headers=owner_a,
        json={
            "movement_type": "IN_PURCHASE",
            "quantity_delta": 3,
            "unit_cost": "32.00",
            "reason": "NF Fornecedor #884",
        },
    )
    assert purchase_res.status_code == 201
    assert purchase_res.json()["resulting_stock"] == 8
    assert Decimal(purchase_res.json()["unit_cost_snapshot"]) == Decimal("32.00")

    # 4. Bloqueio de saldo negativo em saída/ajuste (-9 quando saldo atual é 8)
    neg_attempt = await client.post(
        f"/api/v1/piercing/products/{product_id}/movements",
        headers=owner_a,
        json={
            "movement_type": "ADJUSTMENT",
            "quantity_delta": -9,
            "reason": "Tentativa inválida acima do saldo",
        },
    )
    assert neg_attempt.status_code == 422
    assert neg_attempt.json()["code"] == "INSUFFICIENT_STOCK"

    # 5. Ajuste válido (-6 -> saldo passa a 2, atingindo alerta de estoque mínimo min_stock_alert=2)
    valid_adj = await client.post(
        f"/api/v1/piercing/products/{product_id}/movements",
        headers=owner_a,
        json={
            "movement_type": "ADJUSTMENT",
            "quantity_delta": -6,
            "reason": "Separação para mostruário e avaria de rosca",
        },
    )
    assert valid_adj.status_code == 201
    assert valid_adj.json()["resulting_stock"] == 2

    low_stock_list = await client.get(
        "/api/v1/piercing/products",
        headers=owner_a,
        params={"low_stock_only": "true"},
    )
    assert len(low_stock_list.json()) == 1
    assert low_stock_list.json()[0]["is_low_stock"] is True

    # 6. Proteção de Margem: omissão real de `cost_price` e `unit_cost_snapshot` para RECEPTION e PROFESSIONAL
    for staff_headers in (rec_a, prof_a):
        list_staff = await client.get("/api/v1/piercing/products", headers=staff_headers)
        assert list_staff.status_code == 200
        assert "cost_price" not in list_staff.json()[0]
        assert Decimal(list_staff.json()[0]["sale_price"]) == Decimal("135.00")

        detail_staff = await client.get(
            f"/api/v1/piercing/products/{product_id}", headers=staff_headers
        )
        assert detail_staff.status_code == 200
        assert "cost_price" not in detail_staff.json()

        mov_staff = await client.get(
            f"/api/v1/piercing/products/{product_id}/movements", headers=staff_headers
        )
        assert mov_staff.status_code == 200
        assert len(mov_staff.json()) == 3
        assert all("unit_cost_snapshot" not in m for m in mov_staff.json())

        # Staff bloqueado de criar produto ou movimentar estoque
        assert (
            await client.post(
                f"/api/v1/piercing/products/{product_id}/movements",
                headers=staff_headers,
                json={"movement_type": "ADJUSTMENT", "quantity_delta": 1, "reason": "X"},
            )
        ).status_code == 403

    # 7. Anti-IDOR entre Studio A e Studio B para produtos e Kardex -> 404
    assert (
        await client.get(f"/api/v1/piercing/products/{product_id}", headers=owner_b)
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/piercing/products/{product_id}/movements", headers=owner_b
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/piercing/products/{product_id}/movements",
            headers=owner_b,
            json={"movement_type": "IN_PURCHASE", "quantity_delta": 5, "reason": "IDOR"},
        )
    ).status_code == 404
