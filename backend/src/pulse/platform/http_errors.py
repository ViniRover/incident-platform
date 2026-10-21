from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.responses import JSONResponse

from pulse.platform.errors import (
    ApplicationError,
    Conflict,
    DependencyUnavailable,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthenticated,
)


class ErrorResponse(BaseModel):
    detail: str


ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 429, 503)}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, error: ApplicationError):
        statuses = {
            Conflict: 409,
            Forbidden: 403,
            NotFound: 404,
            Unauthenticated: 401,
            RateLimited: 429,
            DependencyUnavailable: 503,
        }
        headers = {"Cache-Control": "no-store"}
        if isinstance(error, RateLimited):
            headers["Retry-After"] = "60"
        # Preserve domain/presentation separation and inherit the nearest mapped status.
        status = next((statuses[base] for base in type(error).__mro__ if base in statuses), 500)
        detail = str(error) if status != 500 else "Internal server error."
        return JSONResponse({"detail": detail}, status_code=status, headers=headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError):
        return JSONResponse(
            {"detail": "Resource already exists or conflicts with current state."},
            status_code=409,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse(
            {"detail": "Database temporarily unavailable."},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Never reflect passwords, cookies, or other submitted values in a 422 response.
        errors = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            {"detail": errors}, status_code=422, headers={"Cache-Control": "no-store"}
        )
