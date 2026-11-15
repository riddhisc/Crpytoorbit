"""Error contract shared by every endpoint.

Shape: {"error": {"code", "message", "details", "request_id"}}.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging import request_id_var


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id_var.get(),
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_payload(code, message, details))


def _http_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }.get(status_code, "HTTP_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": exc.errors()},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return error_response(
            429, "RATE_LIMITED", "Too many requests. Try again shortly.", {"detail": str(exc)}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return error_response(
                exc.status_code,
                str(detail["code"]),
                str(detail.get("message", "")),
                detail.get("details"),
            )
        message = detail if isinstance(detail, str) else "Request failed."
        return error_response(exc.status_code, _http_code(exc.status_code), message)

    @app.exception_handler(HTTPException)
    async def fastapi_http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return await http_handler(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        return error_response(
            500, "INTERNAL", "Something went wrong on our side.", {"type": type(exc).__name__}
        )
