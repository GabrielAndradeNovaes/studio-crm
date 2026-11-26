from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import ensure_superadmin
from app.core.database import AuditActorsMixin
from app.core.exceptions import NotFoundError
from app.core.timezone import studio_date_range_to_utc
from app.domains.core.studios.repository import PaymentMethodConfigRepository


async def _setup_two_studios(client: AsyncClient) -> dict[str, str]:
    res_a = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Titan Piercing Studio A",
            "owner_name": "Alice Owner",
            "owner_email": "alice@studio-a.com",
            "owner_password": "PasswordStudioA!123",
        },
    )
    studio_a_id = res_a.json()["id"]

    res_b = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Gold Piercing Studio B",
            "owner_name": "Bruno Owner",
            "owner_email": "bruno@studio-b.com",
            "owner_password": "PasswordStudioB!123",
        },
    )
    studio_b_id = res_b.json()["id"]

    client.cookies.clear()
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@studio-a.com", "password": "PasswordStudioA!123"},
    )
    token_a = login_a.json()["access_token"]

    client.cookies.clear()
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "bruno@studio-b.com", "password": "PasswordStudioB!123"},
    )
    token_b = login_b.json()["access_token"]

    return {
        "studio_a_id": studio_a_id,
        "studio_b_id": studio_b_id,
        "token_a": token_a,
        "token_b": token_b,
    }


@pytest.mark.asyncio
async def test_strict_multi_tenant_anti_idor_on_select_update_and_delete(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    ctx = await _setup_two_studios(client)
    token_a = ctx["token_a"]
    token_b = ctx["token_b"]

    # Bruno (Studio B) cria uma piercer na equipe B e lê métodos de pagamento do Studio B
    member_b_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "name": "Bia Piercer B",
            "email": "bia@studio-b.com",
            "password": "BiaPassword!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "50.00",
            "commission_product_pct": "20.00",
        },
    )
    assert member_b_res.status_code == 201
    membership_b_id = member_b_res.json()["membership_id"]

    pm_b_res = await client.get(
        "/api/v1/studios/current/payment-methods",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    pm_b_id = pm_b_res.json()[0]["id"]

    # 1. SELECT cross-tenant: Alice (Studio A) lista equipe e métodos e NÃO enxerga registros de B
    team_a_res = await client.get(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert all(m["membership_id"] != membership_b_id for m in team_a_res.json())

    # 2. UPDATE cross-tenant via API: Alice tenta editar membro ou taxa do Studio B -> 404 Not Found
    idor_patch_team = await client.patch(
        f"/api/v1/team/{membership_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"commission_service_pct": "1.00"},
    )
    assert idor_patch_team.status_code == 404

    idor_put_pm = await client.put(
        f"/api/v1/studios/current/payment-methods/{pm_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"fee_percentage": "9.99"},
    )
    assert idor_put_pm.status_code == 404

    # 3. DELETE cross-tenant via API: Alice tenta desativar membro do Studio B -> 404 Not Found
    idor_delete_team = await client.delete(
        f"/api/v1/team/{membership_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert idor_delete_team.status_code == 404

    # 4. Teste direto no BaseTenantRepository para UPDATE e HARD DELETE cross-tenant
    import uuid

    repo_a = PaymentMethodConfigRepository(db_session, uuid.UUID(ctx["studio_a_id"]))
    with pytest.raises(NotFoundError):
        await repo_a.update_by_id(
            uuid.UUID(pm_b_id), {"fee_percentage": Decimal("15.00")}
        )
    with pytest.raises(NotFoundError):
        await repo_a.hard_delete_by_id(uuid.UUID(pm_b_id))


@pytest.mark.asyncio
async def test_rbac_roles_and_last_owner_protection(client: AsyncClient) -> None:
    ctx = await _setup_two_studios(client)
    owner_token = ctx["token_a"]

    # OWNER cadastra RECEPTION e PROFESSIONAL
    rec_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Renata Recepção",
            "email": "renata@studio-a.com",
            "password": "RenataPassword!123",
            "role": "RECEPTION",
        },
    )
    assert rec_res.status_code == 201

    prof_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Paulo Piercer",
            "email": "paulo@studio-a.com",
            "password": "PauloPassword!123",
            "role": "PROFESSIONAL",
            "commission_service_pct": "40.00",
            "commission_product_pct": "10.00",
        },
    )
    assert prof_res.status_code == 201

    # Último OWNER não pode se desativar nem rebaixar o próprio papel
    my_owner = await client.get(
        "/api/v1/team/me",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_membership_id = my_owner.json()["membership_id"]

    demote_self = await client.patch(
        f"/api/v1/team/{owner_membership_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"role": "RECEPTION"},
    )
    assert demote_self.status_code == 422
    assert demote_self.json()["code"] == "LAST_OWNER_PROTECTED"

    # Login como RECEPTION: não pode ver lista completa com comissões de terceiros nem alterar taxas
    client.cookies.clear()
    rec_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "renata@studio-a.com", "password": "RenataPassword!123"},
    )
    rec_token = rec_login.json()["access_token"]

    forbidden_team = await client.get(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {rec_token}"},
    )
    assert forbidden_team.status_code == 403
    assert forbidden_team.json()["code"] == "INSUFFICIENT_ROLE"

    # Mas RECEPTION acessa /team/directory sem campos de comissão expostos
    directory_res = await client.get(
        "/api/v1/team/directory",
        headers={"Authorization": f"Bearer {rec_token}"},
    )
    assert directory_res.status_code == 200
    assert len(directory_res.json()) == 3
    assert "commission_service_pct" not in directory_res.json()[0]

    forbidden_studio_patch = await client.patch(
        "/api/v1/studios/current",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"name": "Tentativa Indevida"},
    )
    assert forbidden_studio_patch.status_code == 403


@pytest.mark.asyncio
async def test_saas_commercial_governance_suspension_modules_and_timezone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await ensure_superadmin(
        db_session,
        email="super@saas.com",
        password="SuperPassword!123",
        name="Super Admin",
    )
    sa_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "super@saas.com", "password": "SuperPassword!123"},
    )
    sa_token = sa_login.json()["access_token"]

    # SuperAdmin cria estúdio ativo apenas com módulo "piercing"
    create_res = await client.post(
        "/api/v1/admin/studios",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={
            "name": "Onix Body Piercing",
            "slug": "onix-piercing",
            "enabled_modules": ["piercing"],
            "timezone": "America/Sao_Paulo",
            "subscription_status": "ACTIVE",
            "commission_deducts_payment_fee": True,
            "owner_name": "Otávio Dono",
            "owner_email": "otavio@onix.com",
            "owner_password": "OtavioPassword!123",
        },
    )
    assert create_res.status_code == 201
    studio_id = create_res.json()["id"]

    client.cookies.clear()
    owner_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "otavio@onix.com", "password": "OtavioPassword!123"},
    )
    owner_token = owner_login.json()["access_token"]

    # Módulo Piercing ativo -> 200 OK; Módulo Tattoo desativado -> 403 MODULE_DISABLED
    piercing_ok = await client.get(
        "/api/v1/piercing/module-status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert piercing_ok.status_code == 200

    tattoo_blocked = await client.get(
        "/api/v1/tattoo/module-status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert tattoo_blocked.status_code == 403
    assert tattoo_blocked.json()["code"] == "MODULE_DISABLED"

    # SuperAdmin habilita módulo "tattoo" sem nenhuma refatoração estrutural
    enable_tattoo = await client.patch(
        f"/api/v1/admin/studios/{studio_id}",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={"enabled_modules": ["piercing", "tattoo"]},
    )
    assert enable_tattoo.status_code == 200

    tattoo_ok = await client.get(
        "/api/v1/tattoo/module-status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert tattoo_ok.status_code == 200

    # SuperAdmin suspende assinatura do estúdio -> bloqueio operacional imediato com STUDIO_SUSPENDED
    suspend_res = await client.patch(
        f"/api/v1/admin/studios/{studio_id}",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={"subscription_status": "SUSPENDED"},
    )
    assert suspend_res.status_code == 200

    suspended_access = await client.get(
        "/api/v1/studios/current",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert suspended_access.status_code == 403
    assert suspended_access.json()["code"] == "STUDIO_SUSPENDED"

    # Novo login também retorna STUDIO_SUSPENDED
    client.cookies.clear()
    suspended_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "otavio@onix.com", "password": "OtavioPassword!123"},
    )
    assert suspended_login.status_code == 403
    assert suspended_login.json()["code"] == "STUDIO_SUSPENDED"

    # Verifica conversão de fuso horário America/Sao_Paulo (UTC-3) para cortes diários do caixa
    start_utc, end_utc = studio_date_range_to_utc(
        date(2026, 11, 26), date(2026, 11, 26), "America/Sao_Paulo"
    )
    assert start_utc == datetime(2026, 11, 26, 3, 0, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 11, 27, 2, 59, 59, 999999, tzinfo=timezone.utc)

    # Verifica que AuditActorsMixin.created_by permanece NULLABLE (suporte futuro à anamnese pública)
    created_by_col = AuditActorsMixin.created_by.column  # type: ignore[attr-defined]
    assert created_by_col.nullable is True
