from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.enums import StudioRole, SubscriptionStatus


def _validate_login_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise ValueError("Informe um endereço de e-mail válido.")
    return cleaned


LoginEmailStr = Annotated[str, Field(min_length=3, max_length=255), AfterValidator(_validate_login_email)]


class LoginRequest(BaseModel):
    email: LoginEmailStr
    password: str = Field(..., min_length=1, max_length=128)


class SelectStudioRequest(BaseModel):
    selection_token: str
    studio_id: uuid.UUID


class SwitchStudioRequest(BaseModel):
    studio_id: uuid.UUID


class ForgotPasswordRequest(BaseModel):
    email: LoginEmailStr


class AuthenticatedUserSummary(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_superadmin: bool


class StudioMembershipOption(BaseModel):
    studio_id: uuid.UUID
    studio_name: str
    studio_slug: str
    role: StudioRole
    timezone: str
    enabled_modules: list[str]
    subscription_status: SubscriptionStatus
    is_studio_active: bool
    is_operational: bool


class AuthSessionResponse(BaseModel):
    requires_studio_selection: bool = False
    selection_token: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user: AuthenticatedUserSummary
    current_studio: StudioMembershipOption | None = None
    available_studios: list[StudioMembershipOption] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str
