from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        *,
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


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def app_error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "application_error",
        extra={
            "path": request.url.path,
            "code": exc.code,
            "status_code": exc.status_code,
        },
    )
    return app_error_response(exc)


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    logger.warning(
        "http_error",
        extra={
            "path": request.url.path,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="http_error",
            message=str(exc.detail),
        ),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "validation_error",
        extra={
            "path": request.url.path,
            "error_count": len(exc.errors()),
        },
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            code="validation_error",
            message="请求参数不合法。",
            details={"errors": _json_safe(exc.errors())},
        ),
    )


def service_error(exc: Exception) -> AppError:
    message = str(exc)
    if isinstance(exc, ValueError):
        return AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="bad_request",
            message=message,
        )
    if "DEEPSEEK_API_KEY" in message:
        return AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="llm_not_configured",
            message=message,
        )
    if "DeepSeek chat 调用失败" in message:
        return AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="llm_request_failed",
            message=message,
        )
    if "embedding" in message.lower() or "bge" in message.lower():
        return AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="embedding_failed",
            message=message,
        )
    return AppError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message=message,
    )
