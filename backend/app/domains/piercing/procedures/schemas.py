from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_tz_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("Data/hora deve incluir fuso horário explícito (ISO 8601).")
    return dt.astimezone(timezone.utc)


class PiercingProcedureCreateRequest(BaseModel):
    client_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    professional_id: uuid.UUID | None = None
    service_id: uuid.UUID
    jewelry_product_id: uuid.UUID | None = None
    anatomical_site_detail: str = Field(..., min_length=2, max_length=160)
    sterilization_lot: str | None = Field(default=None, max_length=80)
    healing_notes: str | None = Field(default=None, max_length=4000)
    performed_at: datetime | None = None
    downsize_reminder_date: date | None = None

    @field_validator("performed_at")
    @classmethod
    def validate_performed_tz(cls, v: datetime | None) -> datetime | None:
        return _ensure_tz_utc(v)


class PiercingProcedureUpdateRequest(BaseModel):
    jewelry_product_id: uuid.UUID | None = None
    anatomical_site_detail: str | None = Field(default=None, min_length=2, max_length=160)
    sterilization_lot: str | None = Field(default=None, max_length=80)
    healing_notes: str | None = Field(default=None, max_length=4000)
    downsize_reminder_date: date | None = None


class CompleteDownsizeRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


DownsizeWindowFilter = Literal[
    "overdue",
    "next_7_days",
    "next_30_days",
    "all_pending",
]


class PiercingProcedureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    client_whatsapp: str
    appointment_id: uuid.UUID | None
    sale_id: uuid.UUID | None
    professional_id: uuid.UUID
    professional_name: str
    service_id: uuid.UUID
    service_name: str
    jewelry_product_id: uuid.UUID | None
    jewelry_name: str | None
    anatomical_site_detail: str
    sterilization_lot: str | None
    healing_notes: str | None
    performed_at: datetime
    downsize_reminder_date: date | None
    downsize_completed_at: datetime | None
    is_overdue: bool
    days_until_due: int | None
    created_at: datetime
    updated_at: datetime
