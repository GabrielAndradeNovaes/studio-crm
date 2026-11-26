from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy import Date, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    JSONVariant,
    SoftDeleteMixin,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import LeadSource


class Client(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditActorsMixin,
    Base,
):
    __tablename__ = "clients"
    __table_args__ = (
        Index("ix_clients_studio_name", "studio_id", "full_name"),
        Index(
            "uq_clients_studio_whatsapp_active",
            "studio_id",
            "whatsapp",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
    )

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    whatsapp: Mapped[str] = mapped_column(String(24), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)

    lead_source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, name="lead_source_enum", native_enum=False),
        default=LeadSource.OUTRO,
        nullable=False,
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONVariant,
        default=list,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dados do responsável legal (obrigatórios para menores de 18 anos)
    guardian_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    guardian_cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)
    guardian_whatsapp: Mapped[str | None] = mapped_column(String(24), nullable=True)
    guardian_relationship: Mapped[str | None] = mapped_column(String(60), nullable=True)
