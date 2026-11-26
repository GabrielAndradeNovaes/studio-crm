from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import PaymentMethodCode, SUPPORTED_MODULES, SubscriptionStatus
from app.core.timezone import validate_timezone_name

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_and_validate_modules(modules: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(m.strip().lower() for m in modules if m.strip()))
    if not cleaned:
        raise ValueError("Pelo menos um módulo deve estar habilitado (ex.: 'piercing').")
    invalid = [m for m in cleaned if m not in SUPPORTED_MODULES]
    if invalid:
        raise ValueError(
            f"Módulo(s) inválido(s): {', '.join(invalid)}. Permitidos: {', '.join(sorted(SUPPORTED_MODULES))}."
        )
    return cleaned


class StudioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    document: str | None
    phone: str | None
    plan_tier: str
    enabled_modules: list[str]
    timezone: str
    subscription_status: SubscriptionStatus
    trial_ends_at: datetime | None
    commission_deducts_payment_fee: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudioOnboardingRequest(BaseModel):
    studio_name: str = Field(..., min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    document: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str = Field(default="America/Sao_Paulo", max_length=64)

    owner_name: str = Field(..., min_length=2, max_length=150)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: str) -> str:
        return validate_timezone_name(v)

    @field_validator("slug")
    @classmethod
    def check_slug(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        normalized = v.strip().lower()
        if not SLUG_REGEX.match(normalized):
            raise ValueError("O slug deve conter apenas letras minúsculas, números e hífens.")
        return normalized


class StudioUpdateSettingsRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    document: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    commission_deducts_payment_fee: bool | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_timezone_name(v)


class PaymentMethodConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    method: PaymentMethodCode
    label: str
    fee_percentage: Decimal
    fixed_fee: Decimal
    is_active: bool


class PaymentMethodConfigUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=80)
    fee_percentage: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("99.99"))
    fixed_fee: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    is_active: bool | None = None


class SuperadminCreateStudioRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    document: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    plan_tier: str = Field(default="piercing_mvp", max_length=40)
    enabled_modules: list[str] = Field(default_factory=lambda: ["piercing"])
    timezone: str = Field(default="America/Sao_Paulo", max_length=64)
    subscription_status: SubscriptionStatus = SubscriptionStatus.TRIAL
    trial_days: int | None = Field(default=14, ge=0, le=365)
    commission_deducts_payment_fee: bool = False

    owner_name: str = Field(..., min_length=2, max_length=150)
    owner_email: EmailStr
    owner_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: str) -> str:
        return validate_timezone_name(v)

    @field_validator("enabled_modules")
    @classmethod
    def check_modules(cls, v: list[str]) -> list[str]:
        return normalize_and_validate_modules(v)

    @field_validator("slug")
    @classmethod
    def check_slug(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        normalized = v.strip().lower()
        if not SLUG_REGEX.match(normalized):
            raise ValueError("O slug deve conter apenas letras minúsculas, números e hífens.")
        return normalized


class SuperadminUpdateStudioGovernanceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    plan_tier: str | None = Field(default=None, max_length=40)
    enabled_modules: list[str] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    subscription_status: SubscriptionStatus | None = None
    trial_ends_at: datetime | None = None
    commission_deducts_payment_fee: bool | None = None
    is_active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_timezone_name(v)

    @field_validator("enabled_modules")
    @classmethod
    def check_modules(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_and_validate_modules(v)
