from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limit_auth
from app.core.rbac import AuthenticatedPrincipal, get_current_principal
from app.domains.core.auth.schemas import (
    AuthSessionResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    SelectStudioRequest,
    StudioMembershipOption,
    SwitchStudioRequest,
)
from app.domains.core.auth.service import (
    get_current_session_info,
    login_user,
    logout_user,
    refresh_session_token,
    select_studio_session,
    switch_studio_session,
)

router = APIRouter(prefix="/auth", tags=["Auth & Multi-Studio Session"])


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    dependencies=[Depends(rate_limit_auth("login"))],
)
async def login_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await login_user(db, payload, request=request, response=response)


@router.post(
    "/select-studio",
    response_model=AuthSessionResponse,
    dependencies=[Depends(rate_limit_auth("select_studio"))],
)
async def select_studio_endpoint(
    payload: SelectStudioRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await select_studio_session(db, payload, request=request, response=response)


@router.post("/switch-studio", response_model=AuthSessionResponse)
async def switch_studio_endpoint(
    payload: SwitchStudioRequest,
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await switch_studio_session(
        db, principal, payload, request=request, response=response
    )


@router.post(
    "/refresh",
    response_model=AuthSessionResponse,
    dependencies=[Depends(rate_limit_auth("refresh"))],
)
async def refresh_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await refresh_session_token(db, request=request, response=response)


@router.post("/logout", response_model=MessageResponse)
async def logout_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await logout_user(db, request=request, response=response)
    return MessageResponse(message="Sessão encerrada com sucesso.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit_auth("forgot_password"))],
)
async def forgot_password_endpoint(
    _payload: ForgotPasswordRequest,
) -> MessageResponse:
    # Resposta constante para impedir enumeração de e-mails cadastrados
    return MessageResponse(
        message="Se o e-mail estiver cadastrado, enviaremos as instruções de redefinição de senha."
    )


@router.get("/me", response_model=AuthSessionResponse)
async def me_endpoint(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await get_current_session_info(db, principal)


@router.get("/my-studios", response_model=list[StudioMembershipOption])
async def my_studios_endpoint(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[StudioMembershipOption]:
    info = await get_current_session_info(db, principal)
    return info.available_studios
