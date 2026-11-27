from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AppointmentStatus, DepositStatus, PaymentMethodCode


def _ensure_tz_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Data/hora deve incluir fuso horário explícito (ISO 8601).")
    return dt.astimezone(timezone.utc)


class AppointmentCreateRequest(BaseModel):
    client_id: uuid.UUID
    professional_id: uuid.UUID
    module: str = Field(default="piercing", max_length=30)
    service_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime | None = None
    status: AppointmentStatus = AppointmentStatus.AGENDADO
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("start_at")
    @classmethod
    def check_start_tz(cls, v: datetime) -> datetime:
        return _ensure_tz_utc(v)

    @field_validator("end_at")
    @classmethod
    def check_end_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return _ensure_tz_utc(v)


class AppointmentUpdateRequest(BaseModel):
    professional_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("start_at", "end_at")
    @classmethod
    def check_optional_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return _ensure_tz_utc(v)


class AppointmentDepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    payment_method: PaymentMethodCode
    paid_at: datetime | None = None

    @field_validator("paid_at")
    @classmethod
    def check_paid_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return _ensure_tz_utc(v)


class AppointmentDepositRefundRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=255)


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    client_whatsapp: str
    client_is_minor: bool
    professional_id: uuid.UUID
    professional_name: str
    module: str
    service_id: uuid.UUID | None
    service_name: str | None
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    notes: str | None
    deposit_amount: Decimal
    deposit_payment_method: PaymentMethodCode | None
    deposit_status: DepositStatus
    deposit_paid_at: datetime | None
    created_at: datetime
    updated_at: datetime
