from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import LeadSource

NON_DIGITS_RE = re.compile(r"\D+")


def normalize_phone_digits(raw: str, *, field_label: str = "WhatsApp") -> str:
    digits = NON_DIGITS_RE.sub("", raw or "")
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError(f"{field_label} deve conter entre 10 e 15 dígitos numéricos.")
    return digits


def normalize_cpf_digits(raw: str | None, *, field_label: str = "CPF") -> str | None:
    if raw is None or raw.strip() == "":
        return None
    digits = NON_DIGITS_RE.sub("", raw)
    if len(digits) != 11:
        raise ValueError(f"{field_label} deve conter exatamente 11 dígitos numéricos.")
    return digits


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for t in tags:
        item = t.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            cleaned.append(item[:40])
    return cleaned


class ClientCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    whatsapp: str = Field(..., min_length=10, max_length=30)
    email: EmailStr | None = None
    birth_date: date
    cpf: str | None = Field(default=None, max_length=20)
    lead_source: LeadSource = LeadSource.INSTAGRAM
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4000)

    guardian_name: str | None = Field(default=None, max_length=160)
    guardian_cpf: str | None = Field(default=None, max_length=20)
    guardian_whatsapp: str | None = Field(default=None, max_length=30)
    guardian_relationship: str | None = Field(default=None, max_length=60)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v: str | None) -> str | None:
        if v is not None and isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, v: str) -> str:
        return normalize_phone_digits(v, field_label="WhatsApp")

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v: str | None) -> str | None:
        return normalize_cpf_digits(v, field_label="CPF")

    @field_validator("guardian_cpf")
    @classmethod
    def validate_guardian_cpf(cls, v: str | None) -> str | None:
        return normalize_cpf_digits(v, field_label="CPF do responsável")

    @field_validator("guardian_whatsapp")
    @classmethod
    def validate_guardian_whatsapp(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return normalize_phone_digits(v, field_label="WhatsApp do responsável")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)


class ClientUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    whatsapp: str | None = Field(default=None, min_length=10, max_length=30)
    email: EmailStr | None = None
    birth_date: date | None = None
    cpf: str | None = Field(default=None, max_length=20)
    lead_source: LeadSource | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=4000)

    guardian_name: str | None = Field(default=None, max_length=160)
    guardian_cpf: str | None = Field(default=None, max_length=20)
    guardian_whatsapp: str | None = Field(default=None, max_length=30)
    guardian_relationship: str | None = Field(default=None, max_length=60)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v: str | None) -> str | None:
        if v is not None and isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_phone_digits(v, field_label="WhatsApp")

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v: str | None) -> str | None:
        return normalize_cpf_digits(v, field_label="CPF")

    @field_validator("guardian_cpf")
    @classmethod
    def validate_guardian_cpf(cls, v: str | None) -> str | None:
        return normalize_cpf_digits(v, field_label="CPF do responsável")

    @field_validator("guardian_whatsapp")
    @classmethod
    def validate_guardian_whatsapp(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return normalize_phone_digits(v, field_label="WhatsApp do responsável")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_tags(v)


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    full_name: str
    whatsapp: str
    email: str | None
    birth_date: date
    age: int
    is_minor: bool
    cpf: str | None
    lead_source: LeadSource
    tags: list[str]
    notes: str | None
    guardian_name: str | None
    guardian_cpf: str | None
    guardian_whatsapp: str | None
    guardian_relationship: str | None
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
