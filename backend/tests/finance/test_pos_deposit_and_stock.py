from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _setup_pos_env(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Diamond Piercing POS A",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Daniela Owner A",
            "owner_email": "daniela@pos-a.com",
            "owner_password": "PasswordA!123",
        },
    )
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Emerald POS B",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Eduardo Owner B",
            "owner_email": "eduardo@pos-b.com",
            "owner_password": "PasswordB!123",
        },
    )

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "daniela@pos-a.com", "password": "PasswordA!123"},
    )
    owner_a_token = login_a.json()["access_token"]
    owner_a_headers = {"Authorization": f"Bearer {owner_a_token}"}

    rec = await client.post(
        "/api/v1/team",
        headers=owner_a_headers,
        json={
            "name": "Renata Caixa",
            "email": "renata@pos-a.com",
            "password": "PasswordRec!123",
            "role": "RECEPTION",
        },
    )
    assert rec.status_code == 201

    prof = await client.post(
        "/api/v1/team",
        headers=owner_a_headers,
        json={
            "name": "Patrícia Piercer",
            "email": "patricia@pos-a.com",
            "password": "PasswordProf!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "50.00",
            "commission_product_pct": "10.00",
        },
    )
    prof_id = prof.json()["user_id"]

    svc = await client.post(
        "/api/v1/piercing/services",
        headers=owner_a_headers,
        json={
            "name": "Perfuração Septo",
            "anatomical_site": "Septo",
            "duration_minutes": 30,
            "base_price": "110.00",
            "return_days_downsize": 30,
        },
    )
    service_id = svc.json()["id"]

    prod = await client.post(
        "/api/v1/piercing/products",
        headers=owner_a_headers,
        json={
            "sku": "CLICK-TIT-12",
            "name": "Clicker Titânio Articulado",
            "item_type": "JEWELRY",
            "material": "Titânio ASTM F136",
            "cost_price": "25.00",
            "sale_price": "90.00",
            "initial_stock": 3,
            "min_stock_alert": 1,
        },
    )
    product_id = prod.json()["id"]

    cli = await client.post(
        "/api/v1/clients",
        headers=owner_a_headers,
        json={
            "full_name": "Beatriz Cliente",
            "whatsapp": "(11) 98888-9000",
            "birth_date": "1997-02-14",
        },
    )
    client_id = cli.json()["id"]

    client.cookies.clear()
    rec_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "renata@pos-a.com", "password": "PasswordRec!123"},
    )
    rec_a_token = rec_login.json()["access_token"]

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "eduardo@pos-b.com", "password": "PasswordB!123"},
    )
    owner_b_token = login_b.json()["access_token"]

    return {
        "owner_a": owner_a_token,
        "reception_a": rec_a_token,
        "prof_id": prof_id,
        "service_id": service_id,
        "product_id": product_id,
        "client_id": client_id,
        "owner_b": owner_b_token,
    }


@pytest.mark.asyncio
async def test_deposit_day1_checkout_day5_no_double_counting_and_split_payments(
    client: AsyncClient,
) -> None:
    ctx = await _setup_pos_env(client)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}
    rec_a = {"Authorization": f"Bearer {ctx['reception_a']}"}

    day1_utc = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)
    day5_utc = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)

    # Cria agendamento para o Dia 5 e registra sinal de R$ 50,00 no Dia 1 (PIX taxa 0%)
    appt_res = await client.post(
        "/api/v1/appointments",
        headers=rec_a,
        json={
            "client_id": ctx["client_id"],
            "professional_id": ctx["prof_id"],
            "service_id": ctx["service_id"],
            "start_at": day5_utc.isoformat(),
        },
    )
    appt_id = appt_res.json()["id"]

    dep_res = await client.post(
        f"/api/v1/appointments/{appt_id}/deposit",
        headers=rec_a,
        json={
            "amount": "50.00",
            "payment_method": "PIX",
            "paid_at": day1_utc.isoformat(),
        },
    )
    assert dep_res.status_code == 200

    # Verifica Caixa do Dia 1: entraram exatamente R$ 50,00 e Faturamento de Competência ainda é R$ 0,00
    tx_day1 = await client.get(
        "/api/v1/finance/transactions",
        headers=owner_a,
        params={"date_from": "2026-11-01", "date_to": "2026-11-01"},
    )
    assert Decimal(tx_day1.json()["total_inflows"]) == Decimal("50.00")

    dash_day1 = await client.get(
        "/api/v1/finance/dashboard",
        headers=owner_a,
        params={"date_from": "2026-11-01", "date_to": "2026-11-01"},
    )
    assert Decimal(dash_day1.json()["gross_revenue"]) == Decimal("0.00")
    assert Decimal(dash_day1.json()["cash_inflow_net"]) == Decimal("50.00")

    # Registra ficha técnica vinculada ao agendamento antes do fechamento
    proc_res = await client.post(
        "/api/v1/piercing/procedures",
        headers=owner_a,
        json={
            "client_id": ctx["client_id"],
            "appointment_id": appt_id,
            "professional_id": ctx["prof_id"],
            "service_id": ctx["service_id"],
            "jewelry_product_id": ctx["product_id"],
            "anatomical_site_detail": "Septo nasal",
            "performed_at": day5_utc.isoformat(),
        },
    )
    assert proc_res.status_code == 201
    proc_id = proc_res.json()["id"]

    # Tentar pagar valor errado no checkout (ex.: R$ 200 em vez de R$ 150 restantes) -> 422 PAYMENT_TOTAL_MISMATCH
    mismatch_res = await client.post(
        "/api/v1/finance/sales",
        headers=rec_a,
        json={
            "appointment_id": appt_id,
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]},
                {"item_kind": "PIERCING_PRODUCT", "product_id": ctx["product_id"]},
            ],
            "payments": [{"method": "PIX", "amount": "200.00"}],
            "sold_at": day5_utc.isoformat(),
        },
    )
    assert mismatch_res.status_code == 422
    assert mismatch_res.json()["code"] == "PAYMENT_TOTAL_MISMATCH"

    # Fechamento correto no Dia 5: Total R$ 200 (110 + 90) - Sinal R$ 50 = R$ 150 restantes
    # Dividido em R$ 50 Dinheiro (0%) + R$ 100 Crédito (3,99% -> R$ 3,99 taxa, R$ 96,01 líquido)
    sale_res = await client.post(
        "/api/v1/finance/sales",
        headers=rec_a,
        json={
            "appointment_id": appt_id,
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]},
                {"item_kind": "PIERCING_PRODUCT", "product_id": ctx["product_id"]},
            ],
            "payments": [
                {"method": "CASH", "amount": "50.00"},
                {"method": "CREDIT_CARD", "amount": "100.00"},
            ],
            "sold_at": day5_utc.isoformat(),
        },
    )
    assert sale_res.status_code == 201
    sale_staff_json = sale_res.json()
    sale_id = sale_staff_json["id"]

    # RECEPTION não recebe total_cost_snapshot nem unit_cost_snapshot na resposta!
    assert "total_cost_snapshot" not in sale_staff_json
    assert all("unit_cost_snapshot" not in it for it in sale_staff_json["items"])
    assert Decimal(sale_staff_json["subtotal_amount"]) == Decimal("200.00")
    assert Decimal(sale_staff_json["deposit_deducted_amount"]) == Decimal("50.00")
    assert Decimal(sale_staff_json["total_due_amount"]) == Decimal("150.00")

    # Agendamento virou CONCLUIDO com APPLIED_TO_SALE, e procedimento ganhou sale_id!
    appt_after = await client.get(f"/api/v1/appointments/{appt_id}", headers=owner_a)
    assert appt_after.json()["status"] == "CONCLUIDO"
    assert appt_after.json()["deposit_status"] == "APPLIED_TO_SALE"

    procs_after = await client.get(
        "/api/v1/piercing/procedures",
        headers=owner_a,
        params={"appointment_id": appt_id},
    )
    assert procs_after.json()[0]["id"] == proc_id
    assert procs_after.json()[0]["sale_id"] == sale_id

    # Bloqueio de reuso do mesmo agendamento/sinal -> 409 APPOINTMENT_ALREADY_BILLED
    dup_sale = await client.post(
        "/api/v1/finance/sales",
        headers=rec_a,
        json={
            "appointment_id": appt_id,
            "items": [
                {"item_kind": "PIERCING_SERVICE", "service_id": ctx["service_id"]}
            ],
            "payments": [{"method": "PIX", "amount": "110.00"}],
        },
    )
    assert dup_sale.status_code == 409
    assert dup_sale.json()["code"] == "APPOINTMENT_ALREADY_BILLED"

    # Verifica Caixa do Dia 5 isolado (entrou R$ 50 + R$ 96,01 = R$ 146,01 líquido)
    tx_day5 = await client.get(
        "/api/v1/finance/transactions",
        headers=owner_a,
        params={"date_from": "2026-11-05", "date_to": "2026-11-05"},
    )
    assert Decimal(tx_day5.json()["total_inflows"]) == Decimal("146.01")

    # Verifica Dashboard Consolidado [Dia 1 .. Dia 5]:
    # Faturamento Bruto = R$ 200,00 (sem duplicar sinal!)
    # Entradas Líquidas em Caixa = 50,00 + 146,01 = R$ 196,01
    # Taxas = R$ 3,99 | CMV congelado = R$ 25,00 | Comissões (50% de 110 + 10% de 90) = 55 + 9 = R$ 64,00
    dash_full = await client.get(
        "/api/v1/finance/dashboard",
        headers=owner_a,
        params={"date_from": "2026-11-01", "date_to": "2026-11-05"},
    )
    d_json = dash_full.json()
    assert Decimal(d_json["gross_revenue"]) == Decimal("200.00")
    assert Decimal(d_json["cash_inflow_net"]) == Decimal("196.01")
    assert Decimal(d_json["payment_fees_total"]) == Decimal("3.99")
    assert Decimal(d_json["jewelry_cogs_total"]) == Decimal("25.00")
    assert Decimal(d_json["commissions_generated_total"]) == Decimal("64.00")
    assert Decimal(d_json["estimated_net_profit"]) == Decimal("107.01")


@pytest.mark.asyncio
async def test_stock_deduction_insufficient_stock_frozen_cogs_and_standalone_deposit_refund(
    client: AsyncClient,
) -> None:
    ctx = await _setup_pos_env(client)
    owner_a = {"Authorization": f"Bearer {ctx['owner_a']}"}

    sale_date = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)

    # Vende 2 unidades da joia (estoque inicial era 3, custo unitário R$ 25,00 -> CMV = R$ 50,00)
    s1 = await client.post(
        "/api/v1/finance/sales",
        headers=owner_a,
        json={
            "items": [
                {
                    "item_kind": "PIERCING_PRODUCT",
                    "product_id": ctx["product_id"],
                    "quantity": 2,
                }
            ],
            "payments": [{"method": "PIX", "amount": "180.00"}],
            "sold_at": sale_date.isoformat(),
        },
    )
    assert s1.status_code == 201
    assert Decimal(s1.json()["total_cost_snapshot"]) == Decimal("50.00")

    # Saldo no estoque caiu para 1 e Kardex registrou OUT_SALE (-2)
    prod_after = await client.get(
        f"/api/v1/piercing/products/{ctx['product_id']}", headers=owner_a
    )
    assert prod_after.json()["stock_quantity"] == 1

    # Tentativa de vender 2 unidades quando só há 1 -> 422 INSUFFICIENT_STOCK
    insufficient = await client.post(
        "/api/v1/finance/sales",
        headers=owner_a,
        json={
            "items": [
                {
                    "item_kind": "PIERCING_PRODUCT",
                    "product_id": ctx["product_id"],
                    "quantity": 2,
                }
            ],
            "payments": [{"method": "PIX", "amount": "180.00"}],
        },
    )
    assert insufficient.status_code == 422
    assert insufficient.json()["code"] == "INSUFFICIENT_STOCK"

    # Fornecedor aumenta o preço de custo da joia para R$ 48,00 -> CMV histórico permanece congelado em R$ 50,00!
    await client.patch(
        f"/api/v1/piercing/products/{ctx['product_id']}",
        headers=owner_a,
        json={"cost_price": "48.00"},
    )
    dash = await client.get(
        "/api/v1/finance/dashboard",
        headers=owner_a,
        params={"date_from": "2026-11-10", "date_to": "2026-11-10"},
    )
    assert Decimal(dash.json()["jewelry_cogs_total"]) == Decimal("50.00")

    # Estorno de sinal avulso antes de virar venda (`POST /appointments/{id}/deposit/refund`)
    appt2 = await client.post(
        "/api/v1/appointments",
        headers=owner_a,
        json={
            "client_id": ctx["client_id"],
            "professional_id": ctx["prof_id"],
            "start_at": datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc).isoformat(),
        },
    )
    appt2_id = appt2.json()["id"]
    await client.post(
        f"/api/v1/appointments/{appt2_id}/deposit",
        headers=owner_a,
        json={"amount": "40.00", "payment_method": "PIX"},
    )
    refund_dep = await client.post(
        f"/api/v1/appointments/{appt2_id}/deposit/refund",
        headers=owner_a,
        json={"reason": "Cliente desistiu com antecedência"},
    )
    assert refund_dep.status_code == 200
    assert refund_dep.json()["deposit_status"] == "REFUNDED"
    assert refund_dep.json()["status"] == "CANCELADO"
