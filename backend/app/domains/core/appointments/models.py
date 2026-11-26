from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    SoftDeleteMixin,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import AppointmentStatus, DepositStatus, PaymentMethodCode


class Appointment(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditActorsMixin,
    Base,
):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "ix_appointments_studio_prof_start",
            "studio_id",
            "professional_id",
            "start_at",
        ),
        Index(
            "ix_appointments_studio_client",
            "studio_id",
            "client_id",
        ),
        CheckConstraint("end_at > start_at", name="end_after_start"),
        CheckConstraint("deposit_amount >= 0", name="deposit_amount_non_negative"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    module: Mapped[str] = mapped_column(
        String(30), default="piercing", nullable=False
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("piercing_services.id", ondelete="SET NULL"),
        nullable=True,
    )

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status_enum", native_enum=False),
        default=AppointmentStatus.AGENDADO,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estrutura de Sinal pronta para abatimento sem duplicidade na Fase 4 (PDV/Caixa)
    deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    deposit_payment_method: Mapped[PaymentMethodCode | None] = mapped_column(
        Enum(PaymentMethodCode, name="deposit_payment_method_enum", native_enum=False),
        nullable=True,
    )
    deposit_status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus, name="deposit_status_enum", native_enum=False),
        default=DepositStatus.NONE,
        nullable=False,
    )
    deposit_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
