from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, *, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Não autenticado.", code: str = "UNAUTHORIZED") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, code=code, detail=detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Acesso negado.", code: str = "FORBIDDEN") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, code=code, detail=detail)


class NotFoundError(AppError):
    def __init__(
        self, detail: str = "Recurso não encontrado.", code: str = "NOT_FOUND"
    ) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, code=code, detail=detail)


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflito de dados.", code: str = "CONFLICT") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, code=code, detail=detail)


class GoneError(AppError):
    def __init__(
        self,
        detail: str = "Este link expirou ou já foi utilizado.",
        code: str = "LINK_EXPIRED_OR_USED",
    ) -> None:
        super().__init__(status_code=status.HTTP_410_GONE, code=code, detail=detail)


class DomainValidationError(AppError):
    def __init__(
        self, detail: str = "Regra de negócio inválida.", code: str = "DOMAIN_VALIDATION_ERROR"
    ) -> None:
        http_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        super().__init__(status_code=http_422, code=code, detail=detail)


class RateLimitExceededError(AppError):
    def __init__(
        self,
        detail: str = "Muitas tentativas. Aguarde alguns instantes antes de tentar novamente.",
        code: str = "RATE_LIMITED",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, code=code, detail=detail
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )
