"""
kb_writer_tool — writes ArticleData to disk, SQLite, and the BM25 index.

Every call to write_article():
  1. Writes the .md file to kb_storage/ (disk — source of truth for humans/git)
  2. Upserts a KBArticle row in SQLite (fast indexed reads for the API)
  3. Upserts the BM25 index (in-memory + persisted _index.json)
  4. Records a KBVersions row (audit trail)
"""
import logging
from typing import Optional

from kb.repository import AbstractKBRepository, ArticleData

logger = logging.getLogger(__name__)

_kb_repo: Optional[AbstractKBRepository] = None


def set_kb_repo(repo: AbstractKBRepository) -> None:
    global _kb_repo
    _kb_repo = repo


async def write_article(article: ArticleData) -> str:
    """
    Persist an article to all storage layers.
    Returns the relative path of the written article.
    """
    if _kb_repo is None:
        raise RuntimeError("KB repository not initialized.")

    from db.database import AsyncSessionLocal
    from db.repositories import KBArticleRepository, KBVersionRepository

    is_update = (
        article.relative_path is not None
        and _kb_repo.article_exists(article.relative_path)
    )

    # 1. Write .md file to disk (also sets article.version, article.relative_path)
    rel_path = _kb_repo.write_article(article)

    # 2. Upsert KBArticle in SQLite
    try:
        async with AsyncSessionLocal() as session:
            kb_article_repo = KBArticleRepository(session)
            await kb_article_repo.upsert(
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
    except Exception as exc:
        logger.warning("KBArticle DB upsert failed for %s: %s", rel_path, exc)

    # 3. Update BM25 index
    try:
        from tools.bm25_search_tool import _index_manager
        if _index_manager is not None:
            from kb.article_parser import build_article_file_content
            _index_manager.upsert_article(rel_path, build_article_file_content(article))
    except Exception as exc:
        logger.warning("BM25 index update failed for %s: %s", rel_path, exc)

    # 4. Record version audit trail
    try:
        async with AsyncSessionLocal() as session:
            version_repo = KBVersionRepository(session)
            change_type = "updated" if is_update else "created"
            await version_repo.create(
                article_path=rel_path,
                version=article.version,
                change_type=change_type,
            )
    except Exception as exc:
        logger.warning("KB version record failed for %s: %s", rel_path, exc)

    logger.info("Article written: %s (v%d)", rel_path, article.version)
    return rel_path
