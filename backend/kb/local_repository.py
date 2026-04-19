from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from slugify import slugify

from kb.article_parser import parse_article_file, build_article_file_content
from kb.repository import (
    AbstractKBRepository,
    ArticleData,
    ArticleMetadata,
    CategoryNode,
    KBStats,
)


class LocalKBRepository(AbstractKBRepository):
    """Filesystem-based KB storage. Each article is a .md file with YAML frontmatter."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _category_to_path(self, category: str) -> Path:
        """Convert 'Computer Science/AI' → kb_storage/Computer Science/AI/"""
        parts = [p.strip() for p in category.split("/") if p.strip()]
        return self.base_path.joinpath(*parts)

    def _article_relative_path(self, category: str, title: str) -> str:
        """Build relative path for article: 'Computer Science/AI/neural_networks.md'"""
        parts = [p.strip() for p in category.split("/") if p.strip()]
        filename = slugify(title, separator="_") + ".md"
        return "/".join(parts + [filename])

    def write_article(self, article: ArticleData) -> str:
        now = datetime.now(timezone.utc)

        rel_path = article.relative_path or self._article_relative_path(
            article.category, article.title
        )
        abs_path = self.base_path / rel_path

        # Determine version
        if abs_path.exists():
            existing = parse_article_file(abs_path)
            article.version = existing.version + 1
            article.created_at = existing.created_at or now
        else:
            article.version = 1
            article.created_at = article.created_at or now

        article.updated_at = now
        article.relative_path = rel_path

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(build_article_file_content(article), encoding="utf-8")

        return rel_path

    def read_article(self, relative_path: str) -> ArticleData:
        abs_path = self.base_path / relative_path
        if not abs_path.exists():
            raise FileNotFoundError(f"Article not found: {relative_path}")
        article = parse_article_file(abs_path)
        article.relative_path = relative_path
        return article

    def list_articles(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ArticleMetadata]:
        if category:
            search_root = self._category_to_path(category)
        else:
            search_root = self.base_path

        md_files = sorted(search_root.rglob("*.md")) if search_root.exists() else []

        results = []
        for md_file in md_files:
            try:
                article = parse_article_file(md_file)
                rel = str(md_file.relative_to(self.base_path)).replace("\\", "/")
                snippet = article.content[:200].replace("\n", " ").strip()
                results.append(
                    ArticleMetadata(
                        title=article.title,
                        category=article.category,
                        relative_path=rel,
                        tags=article.tags,
                        version=article.version,
                        updated_at=article.updated_at,
                        snippet=snippet,
                    )
                )
            except Exception:
                continue

        total = results[offset : offset + limit]
        return total

    def list_categories(self) -> list[CategoryNode]:
        return self._build_category_tree(self.base_path, "")

    def _build_category_tree(self, path: Path, cat_prefix: str) -> list[CategoryNode]:
        nodes = []
        if not path.exists():
            return nodes

        for entry in sorted(path.iterdir()):
            if not entry.is_dir():
                continue
            cat_path = f"{cat_prefix}/{entry.name}".lstrip("/")
            article_count = len(list(entry.glob("*.md")))
            subcategories = self._build_category_tree(entry, cat_path)
            # Count articles recursively
            total_count = article_count + sum(c.article_count for c in subcategories)
            nodes.append(
                CategoryNode(
                    name=entry.name,
                    path=cat_path,
                    article_count=total_count,
                    subcategories=subcategories,
                )
            )
        return nodes

    def get_stats(self) -> KBStats:
        all_md = list(self.base_path.rglob("*.md"))
        all_dirs = {f.parent for f in all_md}
        total_size = sum(f.stat().st_size for f in all_md)

        last_updated = None
        for f in all_md:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if last_updated is None or mtime > last_updated:
                last_updated = mtime

        return KBStats(
            total_articles=len(all_md),
            total_categories=len(all_dirs),
            last_updated=last_updated,
            total_size_bytes=total_size,
        )

    def get_all_articles_content(self) -> list[tuple[str, str]]:
        results = []
        for md_file in self.base_path.rglob("*.md"):
            try:
                article = parse_article_file(md_file)
                rel = str(md_file.relative_to(self.base_path)).replace("\\", "/")
                full_text = f"{article.title}\n{' '.join(article.tags)}\n{article.content}"
                results.append((rel, full_text))
            except Exception:
                continue
        return results

    def article_exists(self, relative_path: str) -> bool:
        return (self.base_path / relative_path).exists()
