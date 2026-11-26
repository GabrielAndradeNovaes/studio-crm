from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "Piercing & Tattoo Studio SaaS"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = (
        "postgresql+asyncpg://crm_user:change_me_local_dev_password@localhost:5432/crm_saas"
    )

    JWT_SECRET_KEY: str = "dev_only_replace_with_64_char_random_hex_secret_key_0123456789abcdef"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    STUDIO_SELECTION_TOKEN_EXPIRE_MINUTES: int = 5
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    REFRESH_COOKIE_NAME: str = "crm_refresh_token"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    ALLOW_PUBLIC_ONBOARDING: bool = True
    DEFAULT_TRIAL_DAYS: int = 14
    DEFAULT_TIMEZONE: str = "America/Sao_Paulo"

    AUTH_RATE_LIMIT_REQUESTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60

    AUTO_SEED_SUPERADMIN: bool = False
    SUPERADMIN_NAME: str = "SaaS Platform Admin"
    SUPERADMIN_EMAIL: str | None = None
    SUPERADMIN_PASSWORD: str | None = None

    @field_validator("COOKIE_DOMAIN", mode="before")
    @classmethod
    def empty_cookie_domain_to_none(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def enforce_production_security(self) -> "Settings":
        if self.APP_ENV == "production":
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE deve ser obrigatoriamente True em produção.")
            if len(self.JWT_SECRET_KEY) < 32 or self.JWT_SECRET_KEY.startswith("dev_only_"):
                raise ValueError(
                    "JWT_SECRET_KEY insegura ou padrão detectada em ambiente de produção."
                )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
