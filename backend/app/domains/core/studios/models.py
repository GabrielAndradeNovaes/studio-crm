from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    JSONVariant,
    TenantModelMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.core.enums import PaymentMethodCode, SubscriptionStatus


class Studio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "studios"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    document: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    plan_tier: Mapped[str] = mapped_column(String(40), default="piercing_mvp", nullable=False)
    enabled_modules: Mapped[list[str]] = mapped_column(
        JSONVariant,
        default=lambda: ["piercing"],
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(64),
        default="America/Sao_Paulo",
        nullable=False,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum", native_enum=False),
        default=SubscriptionStatus.TRIAL,
        nullable=False,
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    commission_deducts_payment_fee: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PaymentMethodConfig(UUIDPrimaryKeyMixin, TenantModelMixin, TimestampMixin, Base):
    __tablename__ = "payment_method_configs"
    __table_args__ = (
        UniqueConstraint(
            "studio_id",
            "method",
            name="uq_payment_method_configs_studio_method",
        ),
    )

    method: Mapped[PaymentMethodCode] = mapped_column(
        Enum(PaymentMethodCode, name="payment_method_code_enum", native_enum=False),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    fee_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    fixed_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
