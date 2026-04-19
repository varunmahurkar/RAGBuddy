"""
kb.py — knowledge base browsing endpoints.

All list/search/read calls go through SQLite (KBArticleRepository) for
sub-millisecond indexed queries. The disk .md files are the canonical store
for humans/git; SQLite is the operational read store for the API.

GET /api/kb/categories             — category tree
GET /api/kb/articles               — list/search articles (?search=&category=)
GET /api/kb/articles/{path:path}   — read a specific article
GET /api/kb/stats                  — aggregate statistics
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.repositories import KBArticleRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Category tree — still built from LocalKBRepository (directory structure)
# ---------------------------------------------------------------------------

@router.get("/kb/categories")
async def get_categories(request: Request):
    repo = request.app.state.kb_repo
    tree = repo.list_categories()

    def _node(n):
        return {
            "name": n.name,
            "path": n.path,
            "article_count": n.article_count,
            "children": [_node(c) for c in n.subcategories],
        }

    return [_node(n) for n in tree]


# ---------------------------------------------------------------------------
# Article list — indexed SQLite query (fast)
# ---------------------------------------------------------------------------

@router.get("/kb/articles")
async def list_articles(
    search: str = Query(default=""),
    category: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = KBArticleRepository(db)
    articles = await repo.list_articles(search=search, category=category, limit=limit, offset=offset)
    return [
        {
            "title": a.title,
            "category": a.category,
            "tags": a.tags or [],
            "version": a.version,
            "path": a.relative_path,
            "snippet": a.snippet or "",
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in articles
    ]


# ---------------------------------------------------------------------------
# Single article — read from SQLite (content stored in DB)
# ---------------------------------------------------------------------------

@router.get("/kb/articles/{path:path}")
async def read_article(path: str, db: AsyncSession = Depends(get_db)):
    repo = KBArticleRepository(db)
    article = await repo.get_by_path(path)
    if article is None:
        raise HTTPException(404, f"Article not found: {path}")
    return {
        "title": article.title,
        "category": article.category,
        "tags": article.tags or [],
        "version": article.version,
        "sources": article.sources or [],
        "content": article.content,
        "path": article.relative_path,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Stats — from SQLite
# ---------------------------------------------------------------------------

@router.get("/kb/stats")
async def kb_stats(db: AsyncSession = Depends(get_db)):
    repo = KBArticleRepository(db)
    stats = await repo.get_stats()
    return {
        "total_articles": stats["total_articles"],
        "total_categories": stats["total_categories"],
        "last_updated": stats["last_updated"].isoformat() if stats["last_updated"] else None,
    }
