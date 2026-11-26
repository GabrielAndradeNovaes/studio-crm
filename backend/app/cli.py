from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

import app.models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.domains.core.users.models import User
from app.domains.core.users.repository import get_user_by_email


async def ensure_superadmin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    name: str = "SaaS Platform Admin",
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    existing = await get_user_by_email(session, normalized_email)
    if existing is not None:
        changed = False
        if not existing.is_superadmin:
            existing.is_superadmin = True
            changed = True
        if not existing.is_active:
            existing.is_active = True
            changed = True
        if changed:
            await session.commit()
            await session.refresh(existing)
        return existing, False

    user = User(
        name=name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        is_superadmin=True,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def _run_seed_superadmin(args: argparse.Namespace) -> int:
    settings = get_settings()
    email = args.email or settings.SUPERADMIN_EMAIL
    password = args.password or settings.SUPERADMIN_PASSWORD
    name = args.name or settings.SUPERADMIN_NAME

    if not email or not password:
        if args.if_configured:
            print("[cli] SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD não definidos; seed ignorado.")
            return 0
        print(
            "[cli] Erro: defina SUPERADMIN_EMAIL e SUPERADMIN_PASSWORD no .env ou passe --email / --password.",
            file=sys.stderr,
        )
        return 1

    if args.if_configured and not settings.AUTO_SEED_SUPERADMIN:
        print("[cli] AUTO_SEED_SUPERADMIN=false; seed automático ignorado.")
        return 0

    async with AsyncSessionLocal() as session:
        user, created = await ensure_superadmin(
            session, email=email, password=password, name=name
        )
        status_label = "criado" if created else "já existente (permissão garantida)"
        print(f"[cli] SuperAdmin '{user.email}' ({user.id}) {status_label}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI administrativa do SaaS CRM")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_cmd = subparsers.add_parser(
        "seed-superadmin",
        help="Cria ou promove o usuário SuperAdmin inicial da plataforma.",
    )
    seed_cmd.add_argument("--email", type=str, default=None)
    seed_cmd.add_argument("--password", type=str, default=None)
    seed_cmd.add_argument("--name", type=str, default=None)
    seed_cmd.add_argument(
        "--if-configured",
        action="store_true",
        help="Executa silenciosamente apenas se AUTO_SEED_SUPERADMIN=true e variáveis estiverem preenchidas.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "seed-superadmin":
        return asyncio.run(_run_seed_superadmin(args))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
