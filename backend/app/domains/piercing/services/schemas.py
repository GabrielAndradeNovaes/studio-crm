from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PiercingServiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    anatomical_site: str = Field(..., min_length=2, max_length=80)
    duration_minutes: int = Field(default=30, gt=0, le=480)
    base_price: Decimal = Field(..., ge=Decimal("0.00"))
    return_days_downsize: int | None = Field(default=30, ge=0, le=365)
    aftercare_instructions: str | None = Field(default=None, max_length=4000)
    is_active: bool = True


class PiercingServiceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    anatomical_site: str | None = Field(default=None, min_length=2, max_length=80)
    duration_minutes: int | None = Field(default=None, gt=0, le=480)
    base_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    return_days_downsize: int | None = Field(default=None, ge=0, le=365)
    aftercare_instructions: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class PiercingServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    name: str
    anatomical_site: str
    duration_minutes: int
    base_price: Decimal
    return_days_downsize: int | None
    aftercare_instructions: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
