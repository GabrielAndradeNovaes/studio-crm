from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import StudioRole


class TeamMemberCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Obrigatória para novos usuários; opcional se o e-mail já existir em outro estúdio.",
    )
    role: StudioRole
    commission_service_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("100.00")
    )
    commission_product_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("100.00")
    )


class TeamMemberUpdateRequest(BaseModel):
    role: StudioRole | None = None
    commission_service_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.00"), le=Decimal("100.00")
    )
    commission_product_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.00"), le=Decimal("100.00")
    )
    is_active: bool | None = None


class TeamMemberOwnerResponse(BaseModel):
    membership_id: uuid.UUID
    studio_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: StudioRole
    commission_service_pct: Decimal
    commission_product_pct: Decimal
    is_active: bool
    created_at: datetime


class TeamMemberDirectoryResponse(BaseModel):
    """Visão operacional sem expor comissões de terceiros para RECEPTION/PROFESSIONAL."""

    membership_id: uuid.UUID
    studio_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: StudioRole
    is_active: bool
