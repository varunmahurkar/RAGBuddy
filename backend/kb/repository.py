from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ArticleData:
    """Represents a KB article (frontmatter + content)."""
    title: str
    category: str              # e.g. "Computer Science/AI"
    content: str               # markdown body (no frontmatter)
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Relative path within kb_storage (set after write)
    relative_path: Optional[str] = None


@dataclass
class ArticleMetadata:
    """Lightweight article info for listings."""
    title: str
    category: str
    relative_path: str
    tags: list[str]
    version: int
    updated_at: Optional[datetime]
    snippet: str = ""          # first ~200 chars of content


@dataclass
class CategoryNode:
    name: str
    path: str                  # category path, e.g. "Computer Science/AI"
    article_count: int = 0
    subcategories: list["CategoryNode"] = field(default_factory=list)


@dataclass
class KBStats:
    total_articles: int
    total_categories: int
    last_updated: Optional[datetime]
    total_size_bytes: int


class AbstractKBRepository(ABC):
    @abstractmethod
    def write_article(self, article: ArticleData) -> str:
        """Write article to storage. Returns relative path."""

    @abstractmethod
    def read_article(self, relative_path: str) -> ArticleData:
        """Read article by relative path."""

    @abstractmethod
    def list_articles(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ArticleMetadata]:
        """List articles, optionally filtered by category prefix."""

    @abstractmethod
    def list_categories(self) -> list[CategoryNode]:
        """Return tree of categories."""

    @abstractmethod
    def get_stats(self) -> KBStats:
        """Return KB-wide statistics."""

    @abstractmethod
    def get_all_articles_content(self) -> list[tuple[str, str]]:
        """Return (relative_path, full_text) for all articles — used to rebuild BM25 index."""

    @abstractmethod
    def article_exists(self, relative_path: str) -> bool:
        """Check if article exists."""
