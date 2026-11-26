from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import ensure_superadmin
from app.core.config import Settings, get_settings
from app.core.enums import StudioRole
from app.core.security import hash_password, verify_password
from app.domains.core.users.models import StudioMembership


@pytest.mark.asyncio
async def test_argon2id_hashing_and_single_studio_direct_login(
    client: AsyncClient,
) -> None:
    hashed = hash_password("StrongPass!2026")
    assert hashed.startswith("$argon2id$")
    assert verify_password("StrongPass!2026", hashed) is True
    assert verify_password("WrongPass", hashed) is False

    onboard_res = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Valkyrie Piercing Studio",
            "slug": "valkyrie-piercing",
            "timezone": "America/Sao_Paulo",
            "owner_name": "Carla Mendes",
            "owner_email": "carla@valkyrie.com",
            "owner_password": "OwnerPassword!123",
        },
    )
    assert onboard_res.status_code == 201
    studio_data = onboard_res.json()
    assert studio_data["slug"] == "valkyrie-piercing"
    assert studio_data["subscription_status"] == "TRIAL"
    assert studio_data["enabled_modules"] == ["piercing"]
    assert studio_data["commission_deducts_payment_fee"] is False

    # Login com 1 único vínculo deve emitir token imediatamente para esse studio_id
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "carla@valkyrie.com", "password": "OwnerPassword!123"},
    )
    assert login_res.status_code == 200
    body = login_res.json()
    assert body["requires_studio_selection"] is False
    assert body["access_token"] is not None
    assert body["current_studio"]["studio_id"] == studio_data["id"]
    assert body["current_studio"]["role"] == "OWNER"

    # Verifica cookie HttpOnly emitido
    settings = get_settings()
    set_cookie_header = login_res.headers.get("set-cookie", "")
    assert settings.REFRESH_COOKIE_NAME in set_cookie_header
    assert "HttpOnly" in set_cookie_header


@pytest.mark.asyncio
async def test_multi_studio_user_login_selection_and_context_switch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Cria Estúdio A (Marina como OWNER)
    res_a = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Studio Alpha Piercing",
            "owner_name": "Marina Rocha",
            "owner_email": "marina@studios.com",
            "owner_password": "MultiStudioPassword!1",
        },
    )
    assert res_a.status_code == 201
    studio_a_id = res_a.json()["id"]

    # Cria Estúdio B (outro dono) e vincula Marina como PROFESSIONAL com 45% serviço / 15% joia
    res_b = await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Studio Beta BodyArt",
            "owner_name": "Rafael Costa",
            "owner_email": "rafael@beta.com",
            "owner_password": "BetaPassword!1",
        },
    )
    assert res_b.status_code == 201
    studio_b_id = res_b.json()["id"]

    # Login Rafael para convidar Marina por API de equipe (sem precisar informar senha pois Marina já existe!)
    rafael_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rafael@beta.com", "password": "BetaPassword!1"},
    )
    rafael_token = rafael_login.json()["access_token"]

    invite_res = await client.post(
        "/api/v1/team",
        headers={"Authorization": f"Bearer {rafael_token}"},
        json={
            "name": "Marina Rocha",
            "email": "marina@studios.com",
            "role": "PROFESSIONAL",
            "commission_service_pct": "45.00",
            "commission_product_pct": "15.00",
        },
    )
    assert invite_res.status_code == 201

    # Limpa cookies do cliente de teste antes do login da Marina
    client.cookies.clear()

    # Marina tem 2 estúdios -> login deve pedir seleção de estúdio
    marina_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "marina@studios.com", "password": "MultiStudioPassword!1"},
    )
    assert marina_login.status_code == 200
    login_payload = marina_login.json()
    assert login_payload["requires_studio_selection"] is True
    assert login_payload["access_token"] is None
    assert login_payload["selection_token"] is not None
    assert len(login_payload["available_studios"]) == 2

    # Marina seleciona Studio Alpha (OWNER)
    select_res = await client.post(
        "/api/v1/auth/select-studio",
        json={
            "selection_token": login_payload["selection_token"],
            "studio_id": studio_a_id,
        },
    )
    assert select_res.status_code == 200
    session_a = select_res.json()
    assert session_a["current_studio"]["studio_id"] == studio_a_id
    assert session_a["current_studio"]["role"] == "OWNER"
    token_a = session_a["access_token"]

    # Marina troca de contexto em tempo real para Studio Beta (PROFESSIONAL)
    switch_res = await client.post(
        "/api/v1/auth/switch-studio",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"studio_id": studio_b_id},
    )
    assert switch_res.status_code == 200
    session_b = switch_res.json()
    assert session_b["current_studio"]["studio_id"] == studio_b_id
    assert session_b["current_studio"]["role"] == "PROFESSIONAL"
    token_b = switch_res.json()["access_token"]

    # No Studio Beta, Marina consulta o próprio perfil de comissão (/team/me)
    me_team = await client.get(
        "/api/v1/team/me",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert me_team.status_code == 200
    assert Decimal(me_team.json()["commission_service_pct"]) == Decimal("45.00")
    assert Decimal(me_team.json()["commission_product_pct"]) == Decimal("15.00")


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_detection(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/studios/onboarding",
        json={
            "studio_name": "Rotation Piercing Lab",
            "owner_name": "Lucas Lima",
            "owner_email": "lucas@rotation.com",
            "owner_password": "LucasPassword!123",
        },
    )

    settings = get_settings()
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "lucas@rotation.com", "password": "LucasPassword!123"},
    )
    assert login_res.status_code == 200
    first_refresh_cookie = login_res.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert first_refresh_cookie is not None

    # 1ª rotação legítima -> emite novo cookie e invalida o primeiro
    client.cookies.set(settings.REFRESH_COOKIE_NAME, first_refresh_cookie)
    refresh_1 = await client.post("/api/v1/auth/refresh")
    assert refresh_1.status_code == 200
    second_refresh_cookie = refresh_1.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert second_refresh_cookie is not None
    assert second_refresh_cookie != first_refresh_cookie

    # Ataque: tentativa de reutilizar o 1º refresh token já rotacionado
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, first_refresh_cookie)
    replay_res = await client.post("/api/v1/auth/refresh")
    assert replay_res.status_code == 401
    assert replay_res.json()["code"] == "REFRESH_TOKEN_REUSED"

    # Verifica que o 2º token da mesma família também foi revogado por segurança!
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, second_refresh_cookie)
    compromised_family_res = await client.post("/api/v1/auth/refresh")
    assert compromised_family_res.status_code == 401
    assert compromised_family_res.json()["code"] == "REFRESH_TOKEN_REUSED"


@pytest.mark.asyncio
async def test_auth_rate_limiting_and_production_cookie_secure_validation(
    client: AsyncClient,
) -> None:
    settings = get_settings()
    for _ in range(settings.AUTH_RATE_LIMIT_REQUESTS):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.com", "password": "wrongpassword"},
        )
        assert res.status_code == 401

    blocked_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.com", "password": "wrongpassword"},
    )
    assert blocked_res.status_code == 429
    assert blocked_res.json()["code"] == "RATE_LIMITED"

    # Garante que produção bloqueia COOKIE_SECURE=False
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(
            APP_ENV="production",
            COOKIE_SECURE=False,
            JWT_SECRET_KEY="a" * 64,
        )


@pytest.mark.asyncio
async def test_superadmin_seed_and_global_login_without_studio(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await ensure_superadmin(
        db_session,
        email="root@saas.io",
        password="SuperSecretRoot!2026",
        name="Root SaaS",
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "root@saas.io", "password": "SuperSecretRoot!2026"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["is_superadmin"] is True
    assert data["current_studio"] is None
    assert data["access_token"] is not None

    studios_res = await client.get(
        "/api/v1/admin/studios",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert studios_res.status_code == 200
