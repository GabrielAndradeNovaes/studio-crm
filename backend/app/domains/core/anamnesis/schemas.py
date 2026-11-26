from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnamnesisFieldDefinition(BaseModel):
    key: str = Field(..., min_length=1, max_length=60)
    label: str = Field(..., min_length=2, max_length=300)
    type: Literal["boolean", "boolean_with_details", "text", "textarea"] = "boolean"
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=200)
    details_placeholder: str | None = Field(default=None, max_length=200)


class AnamnesisTemplateUpsertRequest(BaseModel):
    module: str = Field(default="piercing", max_length=30)
    title: str = Field(..., min_length=3, max_length=180)
    fields_schema: list[AnamnesisFieldDefinition] = Field(..., min_length=1)
    consent_text: str = Field(..., min_length=20, max_length=10000)


class AnamnesisTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    module: str
    version: int
    title: str
    fields_schema: list[dict[str, Any]]
    consent_text: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AnamnesisRecordCreateRequest(BaseModel):
    client_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    module: str = Field(default="piercing", max_length=30)
    answers: dict[str, Any]
    guardian_signed_name: str | None = Field(default=None, max_length=160)
    consent_accepted: bool = True
    signature_payload: str = Field(..., min_length=2, max_length=250000)


class AnamnesisRecordSummaryResponse(BaseModel):
    """Listagem enxuta sem expor respostas clínicas sensíveis em lote."""

    id: uuid.UUID
    studio_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    appointment_id: uuid.UUID | None
    template_id: uuid.UUID
    template_version: int
    module: str
    guardian_signed_name: str | None
    consent_accepted: bool
    consent_accepted_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime


class AnamnesisRecordDetailResponse(AnamnesisRecordSummaryResponse):
    """Detalhe completo auditado via READ_SENSITIVE."""

    template_title: str
    fields_schema: list[dict[str, Any]]
    consent_text: str
    answers: dict[str, Any]
    consent_ip: str | None
    consent_user_agent: str | None
    signature_payload: str | None


class CreatePublicAnamnesisLinkRequest(BaseModel):
    client_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    module: str = Field(default="piercing", max_length=30)
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class PublicAnamnesisLinkCreatedResponse(BaseModel):
    link_id: uuid.UUID
    raw_token: str
    public_path: str
    expires_at: datetime
    client_id: uuid.UUID
    client_name: str
    client_whatsapp: str


class PublicAnamnesisFormView(BaseModel):
    """Dados mínimos seguros exibidos no celular sem autenticação (zero exposição de CPF/histórico)."""

    studio_name: str
    client_first_name: str
    is_minor: bool
    module: str
    template_title: str
    template_version: int
    fields_schema: list[dict[str, Any]]
    consent_text: str
    expires_at: datetime


class PublicAnamnesisSubmitRequest(BaseModel):
    answers: dict[str, Any]
    guardian_signed_name: str | None = Field(default=None, max_length=160)
    consent_accepted: bool
    signature_payload: str = Field(..., min_length=2, max_length=250000)


class PublicAnamnesisSubmittedResponse(BaseModel):
    record_id: uuid.UUID
    consent_accepted_at: datetime
    message: str
