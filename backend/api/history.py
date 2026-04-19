"""
history.py — query and ingestion history endpoints.

GET /api/history/queries      — paginated query history
GET /api/history/ingestions   — ingestion history with status
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.repositories import IngestionRepository, QueryRepository

router = APIRouter()


@router.get("/history/queries")
async def get_query_history(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    repo = QueryRepository(db)
    records = await repo.list_all(limit=page_size, offset=(page - 1) * page_size)
    return [
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "articles_used": r.articles_used,
            "suggestions": r.suggestions,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/history/ingestions")
async def get_ingestion_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = IngestionRepository(db)
    records = await repo.list_all()
    return [
        {
            "id": r.id,
            "source_name": r.source_name,
            "status": r.status,
            "articles_created": r.articles_created,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in records
    ]
