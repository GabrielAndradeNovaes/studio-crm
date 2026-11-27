from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _setup_finance_governance_env(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Aurum Finance Studio A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Arthur Owner A",
            "owner_email": "arthur@aurum-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Silver Studio B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Silvia Owner B",
            "owner_email": "silvia@silver-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "arthur@aurum-a.com", "password": "PasswordA!123"},
    )
    owner_a_token = login_a.json()["access_token"]
    owner_a = {"Authorization": f"Bearer {owner_a_token}"}

    # Ajusta taxa do Cartão de Crédito para exatos 4.00% para validar cálculos determinísticos
    pms = (await client.get("/api/v1/studios/current/payment-methods", headers=owner_a)).json()
    cc_cfg = next(p for p in pms if p["method"] == "CREDIT_CARD")
    await client.put(
        f"/api/v1/studios/current/payment-methods/{cc_cfg['id']}",
        headers=owner_a,
        json={"fee_percentage": "4.00", "fixed_fee": "0.00"},
    )

    await client.post(
        "/api/v1/team",
        headers=owner_a,
        json={
            "name": "Rita Caixa",
            "email": "rita@aurum-a.com",
            "password": "PasswordRec!123",
            "role": "RECEPTION",
        },
    )
    p1 = await client.post(
        "/api/v1/team",
        headers=owner_a,
        json={
            "name": "Paula Piercer",
            "email": "paula@aurum-a.com",
            "password": "PasswordP1!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "50.00",
            "commission_product_pct": "10.00",
        },
    )
    prof1_id = p1.json()["user_id"]

    p2 = await client.post(
        "/api/v1/team",
        headers=owner_a,
        json={
            "name": "Pietro Piercer 2",
            "email": "pietro@aurum-a.com",
            "password": "PasswordP2!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "40.00",
            "commission_product_pct": "15.00",
        },
    )
    prof2_id = p2.json()["user_id"]

    svc = await client.post(
        "/api/v1/piercing/services",
        headers=owner_a,
        json={
            "name": "Perfuração Nostril",
            "anatomical_site": "Nostril",
            "duration_minutes": 30,
            "base_price": "100.00",
        },
    )
    service_id = svc.json()["id"]

    prod = await client.post(
        "/api/v1/piercing/products",
        headers=owner_a,
        json={
            "sku": "GOLD-NOST-18K",
            "name": "Argola Ouro 18k Nostril",
            "item_type": "JEWELRY",
            "material": "Ouro 18k",
            "cost_price": "40.00",
            "sale_price": "100.00",
            "initial_stock": 10,
            "min_stock_alert": 2,
        },
    )
    product_id = prod.json()["id"]

    client.cookies.clear()
    rec_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rita@aurum-a.com", "password": "PasswordRec!123"},
    )
    rec_token = rec_login.json()["access_token"]

    client.cookies.clear()
    p1_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "paula@aurum-a.com", "password": "PasswordP1!123"},
    )
    p1_token = p1_login.json()["access_token"]

    client.cookies.clear()
    p2_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pietro@aurum-a.com", "password": "PasswordP2!123"},
    )
    p2_token = p2_login.json()["access_token"]

    client.cookies.clear()
    b_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "silvia@silver-b.com", "password": "PasswordB!123"},
    )
    owner_b_token = b_login.json()["access_token"]

    return {
        "owner_a": owner_a_token,
        "reception_a": rec_token,
        "prof1_token": p1_token,
        "prof1_id": prof1_id,
        "prof2_token": p2_token,
        "prof2_id": prof2_id,
        "service_id": service_id,
        "product_id": product_id,
        "owner_b": owner_b_token,
    }


@pytest.mark.asyncio
async def test_mixed_commissions_fee_deduction_payout_and_paid_vs_pending_refund_clawback(
    client: AsyncClient,
) -> None:
    ctx = await _setup_finance_governance_env(client)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}
    prof1 = {"Authorization": f"Bearer {ctx['prof1_token']}"}
    prof2 = {"Authorization": f"Bearer {ctx['prof2_token']}"}

    # 1. Venda 1 com commission_deducts_payment_fee = False (padrão):
    # Serviço R$ 100 (50% = R$ 50) + Joia R$ 100 (10% = R$ 10) pagos no Crédito (4% = R$ 8 taxa)
    sale1 = await client.post(
        "/api/v1/finance/sales",
        headers=owner_a,
        json={
            "professional_id": ctx["prof1_id"],
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]},
                {"item_kind": "PIERCING_PRODUCT", "product_id": ctx["product_id"]},
            ],
            "payments": [{"method": "CREDIT_CARD", "amount": "200.00"}],
        },
    )
    assert sale1.status_code == 201
    sale1_id = sale1.json()["id"]

    p1_comms = (await client.get("/api/v1/finance/my-commissions", headers=prof1)).json()
    assert Decimal(p1_comms["pending_total"]) == Decimal("60.00")
    sale1_comm_ids = [c["id"] for c in p1_comms["items"]]
    assert len(sale1_comm_ids) == 2

    # 2. Repasse de Comissões da Venda 1 -> gera 1 única saída COMMISSION_PAYOUT de R$ 60,00
    payout_res = await client.post(
        "/api/v1/finance/commissions/payout",
        headers=owner_a,
        json={
            "professional_id": ctx["prof1_id"],
            "commission_ids": sale1_comm_ids,
            "payment_method": "PIX",
            "notes": "Fechamento quinzenal",
        },
    )
    assert payout_res.status_code == 200
    assert Decimal(payout_res.json()["total_paid_amount"]) == Decimal("60.00")

    # 3. Ativa commission_deducts_payment_fee = True e realiza Venda 2 para Prof1:
    # Serviço R$ 100 + Joia R$ 100 no Crédito (4% = R$ 8 taxa -> R$ 4 rateados por item -> base R$ 96 cada)
    # Comissões esperadas: 50% de 96 = R$ 48,00 e 10% de 96 = R$ 9,60 (Total = R$ 57,60)
    await client.patch(
        "/api/v1/studios/current",
        headers=owner_a,
        json={"commission_deducts_payment_fee": True},
    )

    sale2 = await client.post(
        "/api/v1/finance/sales",
        headers=owner_a,
        json={
            "professional_id": ctx["prof1_id"],
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]},
                {"item_kind": "PIERCING_PRODUCT", "product_id": ctx["product_id"]},
            ],
            "payments": [{"method": "CREDIT_CARD", "amount": "200.00"}],
        },
    )
    assert sale2.status_code == 201
    sale2_id = sale2.json()["id"]

    p1_after_s2 = (
        await client.get("/api/v1/finance/my-commissions", headers=prof1)
    ).json()
    assert Decimal(p1_after_s2["pending_total"]) == Decimal("57.60")
    assert Decimal(p1_after_s2["paid_total"]) == Decimal("60.00")

    # Prof2 não enxerga comissões da Prof1!
    p2_comms = (
        await client.get("/api/v1/finance/my-commissions", headers=prof2)
    ).json()
    assert Decimal(p2_comms["pending_total"]) == Decimal("0.00")
    assert p2_comms["items"] == []

    # 4. Estorno da Venda 2 (comissões ainda PENDING -> viram REVERSED; estoque devolvido!)
    ref2 = await client.post(
        f"/api/v1/finance/sales/{sale2_id}/refund",
        headers=owner_a,
        json={"reason": "Cancelamento imediato no caixa"},
    )
    assert ref2.status_code == 200
    assert ref2.json()["status"] == "REFUNDED"

    p1_after_ref2 = (
        await client.get("/api/v1/finance/my-commissions", headers=prof1)
    ).json()
    assert Decimal(p1_after_ref2["pending_total"]) == Decimal("0.00")
    assert Decimal(p1_after_ref2["reversed_total"]) == Decimal("57.60")

    # 5. Estorno da Venda 1 (cujas comissões de R$ 60,00 JÁ ESTAVAM PAGAS!):
    # Histórico PAID permanece intacto (R$ 60,00) e nasce lançamento compensatório negativo (-R$ 60,00 PENDING)!
    ref1 = await client.post(
        f"/api/v1/finance/sales/{sale1_id}/refund",
        headers=owner_a,
        json={"reason": "Devolução pós-repasse"},
    )
    assert ref1.status_code == 200

    p1_after_ref1 = (
        await client.get("/api/v1/finance/my-commissions", headers=prof1)
    ).json()
    assert Decimal(p1_after_ref1["paid_total"]) == Decimal("60.00")
    assert Decimal(p1_after_ref1["pending_total"]) == Decimal("-60.00")

    # E o estoque da joia voltou integralmente às 10 unidades iniciais (10 - 1 - 1 + 1 + 1 = 10)!
    prod_final = await client.get(
        f"/api/v1/piercing/products/{ctx['product_id']}", headers=owner_a
    )
    assert prod_final.json()["stock_quantity"] == 10


@pytest.mark.asyncio
async def test_manual_expenses_reversals_daily_register_rbac_and_anti_idor(
    client: AsyncClient,
) -> None:
    ctx = await _setup_finance_governance_env(client)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}
    rec_a = {"Authorization": f"Bearer {ctx['reception_a']}"}
    prof1 = {"Authorization": f"Bearer {ctx['prof1_token']}"}
    owner_b = {"Authorization": f"Bearer {ctx['owner_b']}"}

    # Venda concluída no dia atual: Perfuração R$ 100 + Joia R$ 100 no PIX (taxa 0%)
    sale_res = await client.post(
        "/api/v1/finance/sales",
        headers=rec_a,
        json={
            "professional_id": ctx["prof1_id"],
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]},
                {"item_kind": "PIERCING_PRODUCT", "product_id": ctx["product_id"]},
            ],
            "payments": [{"method": "PIX", "amount": "200.00"}],
        },
    )
    sale_id = sale_res.json()["id"]

    # OWNER lança despesa fixa de aluguel (R$ 50,00) + uma despesa errada (R$ 30,00) e a estorna!
    exp1 = await client.post(
        "/api/v1/finance/transactions",
        headers=owner_a,
        json={
            "category": "FIXED_EXPENSE",
            "description": "Energia elétrica proporcional",
            "amount": "50.00",
            "payment_method": "PIX",
        },
    )
    assert exp1.status_code == 201

    exp_wrong = await client.post(
        "/api/v1/finance/transactions",
        headers=owner_a,
        json={
            "category": "VARIABLE_EXPENSE",
            "description": "Lançamento duplicado por engano",
            "amount": "30.00",
        },
    )
    wrong_tx_id = exp_wrong.json()["id"]

    rev_res = await client.post(
        f"/api/v1/finance/transactions/{wrong_tx_id}/reverse",
        headers=owner_a,
        json={"reason": "Correção de duplicidade"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["type"] == "REVERSAL"
    assert rev_res.json()["cash_flow_direction"] == "INFLOW"

    # DRE Executivo (`OWNER`):
    # Gross Revenue = 200.00 | Fees = 0.00 | COGS = 40.00 | Comissões = 60.00 | Despesas líquidas = 50.00
    # Lucro Líquido Estimado = 200 - 0 - 40 - 60 - 50 = R$ 50.00
    dash = (await client.get("/api/v1/finance/dashboard", headers=owner_a)).json()
    assert Decimal(dash["gross_revenue"]) == Decimal("200.00")
    assert Decimal(dash["jewelry_cogs_total"]) == Decimal("40.00")
    assert Decimal(dash["commissions_generated_total"]) == Decimal("60.00")
    assert Decimal(dash["operating_expenses_total"]) == Decimal("50.00")
    assert Decimal(dash["estimated_net_profit"]) == Decimal("50.00")
    assert Decimal(dash["average_ticket"]) == Decimal("200.00")
    assert dash["completed_sales_count"] == 1

    # Caixa Operacional do Dia para RECEPTION: omite custos, despesas e lucro líquido!
    daily_rec = await client.get("/api/v1/finance/daily-register", headers=rec_a)
    assert daily_rec.status_code == 200
    daily_json = daily_rec.json()
    assert Decimal(daily_json["sales_checkout_gross"]) == Decimal("200.00")
    assert "operating_expenses_total" not in daily_json
    assert "estimated_net_profit" not in daily_json
    assert "total_cost_snapshot" not in daily_json["sales"][0]

    # Bloqueios RBAC estritos (403) para RECEPTION e PROFESSIONAL
    for restricted_url in (
        "/api/v1/finance/dashboard",
        "/api/v1/finance/transactions",
        "/api/v1/finance/commissions",
    ):
        assert (await client.get(restricted_url, headers=rec_a)).status_code == 403
        assert (await client.get(restricted_url, headers=prof1)).status_code == 403

    assert (
        await client.post(
            f"/api/v1/finance/sales/{sale_id}/refund",
            headers=rec_a,
            json={"reason": "Tentativa recepção"},
        )
    ).status_code == 403
    assert (
        await client.get("/api/v1/finance/daily-register", headers=prof1)
    ).status_code == 403

    # Isolamento Multi-Tenant Anti-IDOR (`Studio B` tentando acessar/estornar recursos de `Studio A` -> 404)
    assert (
        await client.get(f"/api/v1/finance/sales/{sale_id}", headers=owner_b)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/finance/sales/{sale_id}/refund",
            headers=owner_b,
            json={"reason": "IDOR"},
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/finance/transactions/{exp1.json()['id']}/reverse",
            headers=owner_b,
            json={"reason": "IDOR"},
        )
    ).status_code == 404
