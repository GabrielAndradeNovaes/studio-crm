from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    SoftDeleteMixin,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import StudioRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Identidade global do usuário na plataforma SaaS.
    Um mesmo usuário (ex.: Body Piercer ou Owner com filiais) pode atuar em múltiplos
    estúdios através de vínculos independentes em `studio_memberships`.
    """

    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StudioMembership(UUIDPrimaryKeyMixin, TenantModelMixin, TimestampMixin, Base):
    """
    Vínculo do usuário por estúdio com RBAC e regras individuais de comissão
    (% sobre serviços de perfuração/sessão e % separada sobre venda de joia/produto).
    """

    __tablename__ = "studio_memberships"
    __table_args__ = (
        UniqueConstraint(
            "studio_id",
            "user_id",
            name="uq_studio_memberships_studio_user",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[StudioRole] = mapped_column(
        Enum(StudioRole, name="studio_role_enum", native_enum=False),
        nullable=False,
    )
    commission_service_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    commission_product_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
