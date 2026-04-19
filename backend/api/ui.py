"""
ui.py — serves the HTMX frontend from FastAPI.

Template structure:
  layout/base.html                     — main shell (sidebar + content slot)
  pages/chat.html                      — chat / RAG query page
  pages/upload.html                    — document upload & ingest page
  pages/knowledge_base.html            — KB browser (3-panel)
  pages/history.html                   — query + ingestion history tabs

  components/kb_category_tree.html     — HTMX fragment: category sidebar tree
  components/kb_article_list.html      — HTMX fragment: article list panel
  components/kb_article_detail.html    — HTMX fragment: single article reader
  components/history_query_list.html   — HTMX fragment: query history cards
  components/history_ingestion_list.html — HTMX fragment: ingestion log rows

Full-page routes detect the HX-Request header:
  - Browser navigation → render layout/base.html wrapping the page template
  - HTMX swap         → render the page template alone (partial swap into #content)
"""
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.repositories import IngestionRepository, KBArticleRepository, QueryRepository

_TMPL_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TMPL_DIR))

router = APIRouter()


def _is_htmx(req: Request) -> bool:
    return req.headers.get("HX-Request") == "true"


def _respond(req: Request, page_template: str, active_nav: str, ctx: dict):
    """
    Return the correct response for a full-page route:
    - HTMX swap  → just the page partial (swaps into #content)
    - Full load  → layout/base.html with the page included via include_partial
    """
    if _is_htmx(req):
        return templates.TemplateResponse(req, page_template, ctx)
    ctx["active"] = active_nav
    ctx["include_partial"] = page_template
    return templates.TemplateResponse(req, "layout/base.html", ctx)


# ── Full-page routes ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return _respond(request, "pages/chat.html", "chat", {})


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return _respond(request, "pages/upload.html", "upload", {})


@router.get("/kb", response_class=HTMLResponse)
async def kb_page(request: Request):
    return _respond(request, "pages/knowledge_base.html", "kb", {})


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return _respond(request, "pages/history.html", "history", {})


# ── HTMX component fragment routes ───────────────────────────────────────────

@router.get("/ui/kb/categories", response_class=HTMLResponse)
async def component_kb_categories(request: Request):
    """Category tree sidebar — loaded on KB page mount."""
    kb_repo = request.app.state.kb_repo
    tree = kb_repo.list_categories()
    return templates.TemplateResponse(request, "components/kb_category_tree.html", {
        "tree": tree,
    })


@router.get("/ui/kb/articles", response_class=HTMLResponse)
async def component_kb_article_list(
    request: Request,
    search: str = Query(default=""),
    category: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Article list panel — filtered by search query or category."""
    repo = KBArticleRepository(db)
    articles = await repo.list_articles(search=search, category=category, limit=100)
    return templates.TemplateResponse(request, "components/kb_article_list.html", {
        "articles": articles,
        "search": search,
        "category": category,
    })


@router.get("/ui/kb/article/{path:path}", response_class=HTMLResponse)
async def component_kb_article_detail(
    request: Request,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    """Single article detail view — loaded when an article is selected."""
    repo = KBArticleRepository(db)
    article = await repo.get_by_path(path)
    if article is None:
        return HTMLResponse(
            '<div style="padding:40px;text-align:center;font-size:13px;color:#484848;">'
            'Article not found: <code style="color:#636363;">' + path + '</code>'
            '</div>',
            status_code=404,
        )
    return templates.TemplateResponse(request, "components/kb_article_detail.html", {
        "article": article,
    })


@router.get("/ui/history/queries", response_class=HTMLResponse)
async def component_history_query_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Query history cards — paginated list of past RAG queries."""
    repo = QueryRepository(db)
    records = await repo.list_all(limit=25, offset=(page - 1) * 25)
    return templates.TemplateResponse(request, "components/history_query_list.html", {
        "records": records,
        "page": page,
    })


@router.get("/ui/history/ingestions", response_class=HTMLResponse)
async def component_history_ingestion_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Ingestion history rows — status of all document ingestion jobs."""
    repo = IngestionRepository(db)
    records = await repo.list_all()
    return templates.TemplateResponse(request, "components/history_ingestion_list.html", {
        "records": records,
    })
