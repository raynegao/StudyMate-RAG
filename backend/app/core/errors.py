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


class ServiceError(Exception):
    """A typed, client-safe failure raised by the service layer."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "service_error"
    public_message = "服务暂时不可用，请稍后重试。"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.details = details or {}
        super().__init__(message or self.public_message)


class InvalidDocumentIdError(ServiceError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_document_id"
    public_message = "document_id 必须是 32 位十六进制字符串。"


class UnsupportedFileTypeError(ServiceError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "unsupported_file_type"
    public_message = "目前只支持上传 PDF 文件。"


class UploadTooLargeError(ServiceError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "upload_too_large"
    public_message = "上传文件超过大小限制。"


class InvalidPdfError(ServiceError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_pdf"
    public_message = "PDF 文件已损坏或格式无效。"


class EncryptedPdfError(ServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "encrypted_pdf"
    public_message = "暂不支持加密 PDF，请先移除密码保护。"


class PdfTextUnavailableError(ServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "pdf_no_extractable_text"
    public_message = "PDF 中没有可解析文本，请确认文件不是空白或纯扫描件。"


class EmbeddingServiceError(ServiceError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "embedding_failed"
    public_message = "Embedding 服务暂时不可用。"


class EmbeddingInputTooLongError(EmbeddingServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "embedding_input_too_long"
    public_message = "文本超过模型输入长度限制，请缩短问题或重新分块资料。"


class VectorStoreError(ServiceError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "vector_store_unavailable"
    public_message = "向量库暂时不可用。"


class DocumentNotFoundError(ServiceError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "document_not_found"
    public_message = "所选文档不存在或已删除，请刷新文档列表后重新选择。"


class DocumentSelectionRequiredError(ServiceError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "document_selection_required"
    public_message = "概括资料前请先选择一份 PDF，不能用全库片段代替整篇资料。"


class SummaryTooLargeError(ServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "summary_too_large"
    public_message = "文档超过当前整篇概括预算（最多 8 批，每批 12000 字符），请拆分 PDF 后再概括；不会只读开头冒充整篇总结。"


class LLMNotConfiguredError(ServiceError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "llm_not_configured"
    public_message = "DeepSeek 服务尚未配置。"


class LLMServiceError(ServiceError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "llm_request_failed"
    public_message = "DeepSeek 服务调用失败，请稍后重试。"


class LLMTimeoutError(ServiceError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    code = "llm_timeout"
    public_message = "生成回答超时，本次请求未自动重试。请稍后再试。"


class LLMOutputLimitError(ServiceError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "llm_output_incomplete"
    public_message = "模型回答达到输出长度上限，未生成完整答案。请缩小概括范围或减少要求后重试。"


class SummaryCitationError(LLMServiceError):
    """The model answered, but without valid page references; the output is discarded."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "summary_citations_invalid"
    public_message = "概括已生成，但未能对应到原文页码，本次结果未采用。请重试或缩小概括要求。"


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
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_payload(
            code="validation_error",
            message="请求参数不合法。",
            details={"errors": _json_safe(exc.errors())},
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_error",
        extra={"path": request.url.path},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(
            code="internal_error",
            message="服务器内部错误，请稍后重试。",
        ),
    )


def service_error(exc: Exception) -> AppError:
    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, ServiceError):
        return AppError(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.public_message,
            details=exc.details,
        )

    logger.exception("unexpected_service_error", exc_info=exc)
    return AppError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="服务器内部错误，请稍后重试。",
    )
