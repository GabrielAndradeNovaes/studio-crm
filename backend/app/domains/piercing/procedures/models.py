from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.timezone import utcnow


class PiercingProcedure(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    AuditActorsMixin,
    Base,
):
    """
    Registro técnico-sanitário de perfuração realizada.
    Observação arquitetural: vincular `jewelry_product_id` aqui registra rastreabilidade
    clínica, mas NÃO dá baixa em `piercing_products.stock_quantity` (a baixa de estoque
    ocorre exclusivamente no fechamento de venda do PDV na Fase 4).
    """

    __tablename__ = "piercing_procedures"
    __table_args__ = (
        Index("ix_piercing_procedures_studio_client", "studio_id", "client_id"),
        Index(
            "ix_piercing_procedures_studio_downsize",
            "studio_id",
            "downsize_completed_at",
            "downsize_reminder_date",
        ),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    jewelry_product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_products.id", ondelete="SET NULL"),
        nullable=True,
    )

    anatomical_site_detail: Mapped[str] = mapped_column(String(160), nullable=False)
    sterilization_lot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    healing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    downsize_reminder_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    downsize_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
