from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import StudioRole, SubscriptionStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class SelectStudioRequest(BaseModel):
    selection_token: str
    studio_id: uuid.UUID


class SwitchStudioRequest(BaseModel):
    studio_id: uuid.UUID


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class AuthenticatedUserSummary(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
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
