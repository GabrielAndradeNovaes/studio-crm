from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limit_auth
from app.domains.core.anamnesis.schemas import (
    PublicAnamnesisFormView,
    PublicAnamnesisSubmitRequest,
    PublicAnamnesisSubmittedResponse,
)
from app.domains.core.anamnesis.service import (
    get_public_anamnesis_form,
    submit_public_anamnesis_form,
)

router = APIRouter(
    prefix="/public/anamnesis",
    tags=["Public Self-Service Anamnesis"],
)


@router.get(
    "/{token}",
    response_model=PublicAnamnesisFormView,
    dependencies=[Depends(rate_limit_auth("public_anamnesis_view"))],
)
async def view_public_anamnesis_endpoint(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicAnamnesisFormView:
    return await get_public_anamnesis_form(db, token)


@router.post(
    "/{token}",
    response_model=PublicAnamnesisSubmittedResponse,
    dependencies=[Depends(rate_limit_auth("public_anamnesis_submit"))],
)
async def submit_public_anamnesis_endpoint(
    token: str,
    payload: PublicAnamnesisSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PublicAnamnesisSubmittedResponse:
    return await submit_public_anamnesis_form(
        db, token, payload, request=request
    )
