from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse, RuntimeConfigResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="studymate-rag-api")


@router.get("/api/config", response_model=RuntimeConfigResponse)
async def runtime_config() -> RuntimeConfigResponse:
    return RuntimeConfigResponse(
        knowledge_base_name=settings.knowledge_base_name,
        chat_mode=settings.chat_mode,
        llm_provider=settings.llm_provider,
        max_upload_size_mb=settings.max_upload_size_mb,
        default_top_k=settings.default_top_k,
        chat_request_timeout_seconds=settings.chat_request_timeout_seconds,
        summary_request_timeout_seconds=settings.summary_request_timeout_seconds,
    )
