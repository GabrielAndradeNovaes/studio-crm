from __future__ import annotations

from fastapi import APIRouter

from app.domains.core.auth.router import router as auth_router
from app.domains.core.studios.admin_router import router as admin_studios_router
from app.domains.core.studios.router import router as studios_router
from app.domains.core.users.router import router as team_router
from app.domains.piercing.router import router as piercing_router
from app.domains.tattoo.router import router as tattoo_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(studios_router)
api_v1_router.include_router(admin_studios_router)
api_v1_router.include_router(team_router)
api_v1_router.include_router(piercing_router)
api_v1_router.include_router(tattoo_router)
