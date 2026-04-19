from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter

from kb.repository import ArticleData


def parse_article_file(file_path: Path) -> ArticleData:
    """Parse a .md file with YAML frontmatter into an ArticleData object."""
    post = frontmatter.load(str(file_path))

    tags = post.metadata.get("tags", [])
    sources = post.metadata.get("sources", [])
    version = int(post.metadata.get("version", 1))

    created_at = _parse_dt(post.metadata.get("created_at"))
    updated_at = _parse_dt(post.metadata.get("updated_at"))

    relative_path = post.metadata.get("_relative_path")

    return ArticleData(
        title=post.metadata.get("title", file_path.stem.replace("_", " ").title()),
        category=post.metadata.get("category", "Uncategorized"),
        content=post.content,
        tags=tags if isinstance(tags, list) else [tags],
        sources=sources if isinstance(sources, list) else [sources],
        version=version,
        created_at=created_at,
        updated_at=updated_at,
        relative_path=relative_path,
    )


def build_article_file_content(article: ArticleData) -> str:
    """Serialize an ArticleData object to frontmatter + markdown string."""
    now = datetime.now(timezone.utc).isoformat()
    created = article.created_at.isoformat() if article.created_at else now
    updated = article.updated_at.isoformat() if article.updated_at else now

    metadata = {
        "title": article.title,
        "category": article.category,
        "tags": article.tags,
        "sources": article.sources,
        "version": article.version,
        "created_at": created,
        "updated_at": updated,
    }
    if article.relative_path:
        metadata["_relative_path"] = article.relative_path

    post = frontmatter.Post(article.content, **metadata)
    return frontmatter.dumps(post)


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
