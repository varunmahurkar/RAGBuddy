"""
generate_frontmatter skill — builds the YAML frontmatter dict for a KB article.
Pure Python, no Claude call needed.
"""
from datetime import datetime, timezone
from typing import Optional


def generate_frontmatter(
    title: str,
    category: str,
    tags: list[str],
    sources: list[str],
    version: int = 1,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
) -> dict:
    """
    Build a frontmatter metadata dict for a KB article.
    """
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "category": category,
        "tags": sorted(set(tags)),
        "sources": sources,
        "version": version,
        "created_at": (created_at or now).isoformat(),
        "updated_at": (updated_at or now).isoformat(),
    }
