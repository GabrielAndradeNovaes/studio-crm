from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    AuditActorsMixin,
    Base,
    SoftDeleteMixin,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class PiercingService(
    UUIDPrimaryKeyMixin,
    TenantModelMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditActorsMixin,
    Base,
):
    __tablename__ = "piercing_services"
    __table_args__ = (
        Index("ix_piercing_services_studio_site", "studio_id", "anatomical_site"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("base_price >= 0", name="base_price_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    anatomical_site: Mapped[str] = mapped_column(String(80), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    return_days_downsize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aftercare_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
