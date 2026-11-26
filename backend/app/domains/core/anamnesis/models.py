from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    JSONVariant,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.timezone import utcnow


class AnamnesisTemplate(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    AuditActorsMixin,
    Base,
):
    __tablename__ = "anamnesis_templates"
    __table_args__ = (
        UniqueConstraint(
            "studio_id",
            "module",
            "version",
            name="uq_anamnesis_templates_studio_module_version",
        ),
        Index("ix_anamnesis_templates_studio_mod_active", "studio_id", "module", "is_active"),
    )

    module: Mapped[str] = mapped_column(String(30), default="piercing", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    fields_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONVariant, nullable=False
    )
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AnamnesisRecord(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    AuditActorsMixin,
    Base,
):
    """
    Ficha clínica sensível (LGPD Art. 11).
    `created_by` e `updated_by` são NULLABLE para suportar autoatendimento público.
    Quando `consent_accepted == True`, o registro torna-se estritamente imutável.
    """

    __tablename__ = "anamnesis_records"
    __table_args__ = (
        Index("ix_anamnesis_records_studio_client", "studio_id", "client_id"),
        Index("ix_anamnesis_records_studio_appt", "studio_id", "appointment_id"),
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
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("anamnesis_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    module: Mapped[str] = mapped_column(String(30), default="piercing", nullable=False)

    answers: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    guardian_signed_name: Mapped[str | None] = mapped_column(String(160), nullable=True)

    consent_accepted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent_user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    signature_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnamnesisPublicLink(UUIDPrimaryKeyMixin, TenantModelMixin, Base):
    """Link temporário de uso único para preenchimento pelo próprio cliente no celular."""

    __tablename__ = "anamnesis_public_links"
    __table_args__ = (
        Index("ix_anamnesis_public_links_studio_client", "studio_id", "client_id"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("anamnesis_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resulting_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("anamnesis_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
