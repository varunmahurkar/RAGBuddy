"""
health.py — health check and model observability endpoints.

GET /api/health         — basic health check (DB + KB status)
GET /api/health/models  — active model assignments for all agents
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import settings
from tools.bm25_search_tool import _index_manager

router = APIRouter()


@router.get("/health")
async def health():
    article_count = _index_manager.article_count if _index_manager else 0
    return JSONResponse({"status": "ok", "kb_articles": article_count})


@router.get("/health/models")
async def model_config():
    """
    Expose active model assignments and scaling config.
    Useful for verifying .env overrides are applied correctly without reading logs.
    """
    return JSONResponse({
        "agents": {
            "structuring": {
                "model": settings.structuring_model,
                "role": "Converts documents into KB articles (background)",
            },
            "synthesis": {
                "model": settings.synthesis_model,
                "role": "Streams grounded answers to users",
            },
            "suggestion": {
                "model": settings.suggestion_model,
                "role": "Identifies KB gaps after answering",
            },
        },
        "skills": {
            "model": settings.skills_model,
            "role": "categorize, summarize, extract_entities, detect_gaps",
        },
        "retry": {
            "sdk_max_retries": settings.api_max_retries,
            "app_base_delay_s": settings.api_retry_base_delay,
            "app_max_delay_s": settings.api_retry_max_delay,
        },
        "parallel_ingestion": {
            "max_concurrent": settings.max_parallel_ingestions,
        },
    })
