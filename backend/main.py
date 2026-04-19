import logging
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from api.ui import router as ui_router
from config import settings
from db.database import init_db
from kb.index_manager import IndexManager
from kb.local_repository import LocalKBRepository
from services.document_service import DocumentService
from services.ingestion_service import IngestionService
from services.query_service import QueryService
from tools.bm25_search_tool import set_index_manager
from tools.kb_writer_tool import set_kb_repo

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


async def _sync_db_from_disk(kb_repo) -> None:
    """
    Populate the SQLite kb_articles table from .md files on disk when the DB
    is empty. This handles:
      - First startup on an existing KB directory
      - DB file deleted/reset while .md files remain on disk

    Skips if the DB already has articles (normal operation).
    """
    from db.database import AsyncSessionLocal
    from db.repositories import KBArticleRepository
    from kb.article_parser import parse_article_file

    async with AsyncSessionLocal() as session:
        repo = KBArticleRepository(session)
        count = await repo.count()

    disk_articles = kb_repo.get_all_articles_content()

    if count == 0 and disk_articles:
        logger.info("SQLite KB table empty — syncing %d articles from disk…", len(disk_articles))
        synced = 0
        for rel_path, _ in disk_articles:
            try:
                abs_path = kb_repo.base_path / rel_path
                article = parse_article_file(abs_path)
                article.relative_path = rel_path
                async with AsyncSessionLocal() as session:
                    repo = KBArticleRepository(session)
                    await repo.upsert(
                        title=article.title,
                        category=article.category,
                        relative_path=rel_path,
                        content=article.content,
                        tags=article.tags,
                        sources=article.sources,
                        version=article.version,
                        created_at=article.created_at,
                        updated_at=article.updated_at,
                    )
                synced += 1
            except Exception as exc:
                logger.warning("Skipping %s during sync: %s", rel_path, exc)
        logger.info("Synced %d articles to SQLite.", synced)
    else:
        logger.info("SQLite KB table: %d articles (no sync needed).", count)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting RAGBuddy API…")

    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.kb_path.mkdir(parents=True, exist_ok=True)

    # Database
    await init_db()
    logger.info("Database initialized.")

    # KB repository (filesystem)
    kb_repo = LocalKBRepository(settings.kb_path)
    app.state.kb_repo = kb_repo
    set_kb_repo(kb_repo)

    # BM25 index — load from disk or rebuild from KB
    index_manager = IndexManager(settings.kb_path)
    if not index_manager.load():
        logger.info("BM25 index not found — rebuilding from KB…")
        index_manager.build_from_repository(kb_repo)
    set_index_manager(index_manager)
    app.state.index_manager = index_manager

    # Sync SQLite KB table from disk if DB is empty but .md files exist
    # (handles first run after migration, or DB deletion/reset)
    await _sync_db_from_disk(kb_repo)

    # OpenAI client — shared across all agents.
    # max_retries configures SDK-level retry (used by streaming SynthesisAgent).
    # Non-streaming agents additionally use _call_with_retry() at the app layer.
    client = openai.AsyncOpenAI(
        api_key=settings.openai_api_key,
        max_retries=settings.api_max_retries,
    )

    # Log active model assignments at startup for observability
    logger.info(
        "Models — structuring: %s | synthesis: %s | suggestion: %s | skills: %s",
        settings.structuring_model,
        settings.synthesis_model,
        settings.suggestion_model,
        settings.skills_model,
    )
    logger.info(
        "Retry: max=%d, base_delay=%.1fs, max_delay=%.1fs | Parallel ingestion: max=%d",
        settings.api_max_retries, settings.api_retry_base_delay,
        settings.api_retry_max_delay, settings.max_parallel_ingestions,
    )

    # Services
    app.state.settings = settings
    app.state.document_service = DocumentService(settings.uploads_path)
    app.state.ingestion_service = IngestionService(
        client=client,
        kb_repo=kb_repo,
        structuring_model=settings.structuring_model,
        max_parallel=settings.max_parallel_ingestions,
    )
    app.state.query_service = QueryService(
        client=client,
        semantic_rerank_enabled=settings.semantic_rerank_enabled,
        synthesis_model=settings.synthesis_model,
        suggestion_model=settings.suggestion_model,
    )

    logger.info("KB storage: %s (%d articles)", settings.kb_path, index_manager.article_count)
    logger.info("Uploads dir: %s", settings.uploads_path)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down RAGBuddy API.")


app = FastAPI(
    title="RAGBuddy API",
    description="Wikipedia-like Agentic RAG Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AUTH MIDDLEWARE SLOT — uncomment for production:
# from middleware.jwt_auth import JWTAuthMiddleware
# app.add_middleware(JWTAuthMiddleware, secret_key=settings.JWT_SECRET)

app.include_router(ui_router)   # UI routes: /, /upload, /kb, /history, /ui/*
app.include_router(api_router)  # API routes: /api/*
