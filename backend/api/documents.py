"""
documents.py — upload and ingest endpoints.

POST /api/documents/upload         — save uploaded file to staging area
POST /api/documents/ingest         — run ingestion pipeline for one file (background task)
POST /api/documents/ingest/batch   — run ingestion for multiple files in parallel
GET  /api/documents                — list uploaded source documents
"""
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.repositories import IngestionRepository
from services.document_service import DocumentService
from services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _doc_service(request: Request) -> DocumentService:
    return request.app.state.document_service


def _ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    doc_service: DocumentService = Depends(_doc_service),
):
    if not DocumentService.is_allowed(file.filename or ""):
        raise HTTPException(400, "Unsupported file type. Allowed: pdf, docx, txt, md")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit")

    saved_path = await doc_service.save_upload(file.filename, data)
    return JSONResponse({"filename": file.filename, "size": len(data), "path": str(saved_path)})


# ---------------------------------------------------------------------------
# Ingest (triggers background pipeline)
# ---------------------------------------------------------------------------

@router.post("/documents/ingest")
async def ingest_document(
    body: dict,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    doc_service: DocumentService = Depends(_doc_service),
    ing_service: IngestionService = Depends(_ingestion_service),
):
    filename = body.get("filename")
    if not filename:
        raise HTTPException(400, "filename required")

    upload_path = Path(request.app.state.settings.uploads_path) / filename
    if not upload_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    ing_repo = IngestionRepository(db)
    record = await ing_repo.create(
        source_path=str(upload_path),
        source_name=filename,
    )

    async def _run():
        await ing_service.ingest(upload_path, record.id)

    background_tasks.add_task(_run)

    return JSONResponse(
        {"ingestion_id": record.id, "status": "pending", "filename": filename},
        status_code=202,
    )


# ---------------------------------------------------------------------------
# Batch ingest (parallel, bounded by semaphore in IngestionService)
# ---------------------------------------------------------------------------

@router.post("/documents/ingest/batch")
async def ingest_documents_batch(
    body: dict,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ing_service: IngestionService = Depends(_ingestion_service),
):
    """
    Ingest multiple previously-uploaded files in parallel.
    Body: {"filenames": ["file1.pdf", "file2.pdf", ...]}
    Returns 202 with array of ingestion_ids.
    """
    filenames = body.get("filenames", [])
    if not filenames:
        raise HTTPException(400, "filenames list required")
    if len(filenames) > 20:
        raise HTTPException(400, "Maximum 20 files per batch request")

    uploads_path = request.app.state.settings.uploads_path
    ing_repo = IngestionRepository(db)

    file_records: list[tuple[Path, int]] = []
    for filename in filenames:
        upload_path = Path(uploads_path) / filename
        if not upload_path.exists():
            raise HTTPException(404, f"File not found: {filename}")
        record = await ing_repo.create(
            source_path=str(upload_path),
            source_name=filename,
        )
        file_records.append((upload_path, record.id))

    async def _run_batch():
        await ing_service.ingest_many(file_records)

    background_tasks.add_task(_run_batch)

    return JSONResponse(
        {
            "ingestion_ids": [r[1] for r in file_records],
            "filenames": filenames,
            "status": "pending",
        },
        status_code=202,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/documents")
async def list_documents(doc_service: DocumentService = Depends(_doc_service)):
    return await doc_service.list_uploads()
