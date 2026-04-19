from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, desc, or_, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, IngestionHistory, KBArticle, KBVersions, QueryHistory


# ── Ingestion ──────────────────────────────────────────────────────────────────

class IngestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, source_path: str, source_name: str) -> IngestionHistory:
        record = IngestionHistory(
            source_path=source_path,
            source_name=source_name,
            status="pending",
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update_status(
        self,
        record_id: int,
        status: str,
        articles_created: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        record = await self.session.get(IngestionHistory, record_id)
        if record:
            record.status = status
            record.articles_created = articles_created
            record.error_message = error_message
            if status in ("completed", "failed"):
                record.completed_at = datetime.now(timezone.utc)
            await self.session.commit()

    async def get(self, record_id: int) -> Optional[IngestionHistory]:
        return await self.session.get(IngestionHistory, record_id)

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[IngestionHistory]:
        result = await self.session.execute(
            select(IngestionHistory)
            .order_by(desc(IngestionHistory.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


# ── Query history ──────────────────────────────────────────────────────────────

class QueryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        question: str,
        answer: str,
        articles_used: Optional[list] = None,
        suggestions: Optional[list] = None,
        latency_ms: Optional[int] = None,
    ) -> QueryHistory:
        record = QueryHistory(
            question=question,
            answer=answer,
            articles_used=articles_used,
            suggestions=suggestions,
            latency_ms=latency_ms,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[QueryHistory]:
        result = await self.session.execute(
            select(QueryHistory)
            .order_by(desc(QueryHistory.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


# ── KB versions ────────────────────────────────────────────────────────────────

class KBVersionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        article_path: str,
        version: int,
        change_type: str,
        changed_by: str = "system",
    ) -> KBVersions:
        record = KBVersions(
            article_path=article_path,
            version=version,
            change_type=change_type,
            changed_by=changed_by,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_latest_version(self, article_path: str) -> int:
        result = await self.session.execute(
            select(KBVersions.version)
            .where(KBVersions.article_path == article_path)
            .order_by(desc(KBVersions.version))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row if row is not None else 0


# ── KB articles (NEW) ──────────────────────────────────────────────────────────

class KBArticleRepository:
    """
    Fast, indexed access to KB article metadata and content via SQLite.

    All API list/search/read calls go through here — no filesystem scans.
    Data is written by kb_writer_tool.write_article() on every create/update.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        title: str,
        category: str,
        relative_path: str,
        content: str,
        tags: Optional[list] = None,
        sources: Optional[list] = None,
        version: int = 1,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> KBArticle:
        """
        Insert or update a KB article row.
        Uses SQLite's INSERT OR REPLACE via on_conflict_do_update.
        """
        now = datetime.now(timezone.utc)
        snippet = content[:300].replace("\n", " ").strip() if content else ""

        stmt = (
            sqlite_insert(KBArticle)
            .values(
                title=title,
                category=category,
                relative_path=relative_path,
                content=content,
                snippet=snippet,
                tags=tags or [],
                sources=sources or [],
                version=version,
                created_at=created_at or now,
                updated_at=updated_at or now,
            )
            .on_conflict_do_update(
                index_elements=["relative_path"],
                set_={
                    "title": title,
                    "category": category,
                    "content": content,
                    "snippet": snippet,
                    "tags": tags or [],
                    "sources": sources or [],
                    "version": version,
                    "updated_at": updated_at or now,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

        result = await self.session.execute(
            select(KBArticle).where(KBArticle.relative_path == relative_path)
        )
        return result.scalar_one()

    async def get_by_path(self, relative_path: str) -> Optional[KBArticle]:
        result = await self.session.execute(
            select(KBArticle).where(KBArticle.relative_path == relative_path)
        )
        return result.scalar_one_or_none()

    async def list_articles(
        self,
        search: str = "",
        category: str = "",
        limit: int = 200,
        offset: int = 0,
    ) -> list[KBArticle]:
        """
        Fast indexed query for article listings.
        - category: prefix match on category path
        - search: case-insensitive match on title or tags
        """
        q = select(KBArticle).order_by(desc(KBArticle.updated_at))

        if category:
            q = q.where(KBArticle.category.startswith(category))

        if search:
            term = f"%{search.lower()}%"
            q = q.where(
                or_(
                    func.lower(KBArticle.title).like(term),
                    func.lower(KBArticle.category).like(term),
                )
            )

        q = q.limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(KBArticle))
        return result.scalar_one()

    async def get_stats(self) -> dict:
        total = await self.count()
        cat_result = await self.session.execute(
            select(func.count(func.distinct(KBArticle.category))).select_from(KBArticle)
        )
        categories = cat_result.scalar_one()
        last_result = await self.session.execute(
            select(KBArticle.updated_at).order_by(desc(KBArticle.updated_at)).limit(1)
        )
        last_updated = last_result.scalar_one_or_none()
        return {
            "total_articles": total,
            "total_categories": categories,
            "last_updated": last_updated,
        }

    async def delete_by_path(self, relative_path: str) -> None:
        record = await self.get_by_path(relative_path)
        if record:
            await self.session.delete(record)
            await self.session.commit()


# ── Documents (NEW) ────────────────────────────────────────────────────────────

class DocumentRepository:
    """
    Tracks uploaded source documents in SQLite.
    Replaces the filesystem-scan approach for document listings.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        filename: str,
        size_bytes: int,
        extension: str,
        path: str,
    ) -> Document:
        """Insert or update a document row (idempotent on filename)."""
        stmt = (
            sqlite_insert(Document)
            .values(
                filename=filename,
                size_bytes=size_bytes,
                extension=extension,
                path=path,
            )
            .on_conflict_do_update(
                index_elements=["filename"],
                set_={
                    "size_bytes": size_bytes,
                    "path": path,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

        result = await self.session.execute(
            select(Document).where(Document.filename == filename)
        )
        return result.scalar_one()

    async def list_all(self, limit: int = 200, offset: int = 0) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .order_by(desc(Document.uploaded_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_filename(self, filename: str) -> Optional[Document]:
        result = await self.session.execute(
            select(Document).where(Document.filename == filename)
        )
        return result.scalar_one_or_none()

    async def delete_by_filename(self, filename: str) -> bool:
        record = await self.get_by_filename(filename)
        if record:
            await self.session.delete(record)
            await self.session.commit()
            return True
        return False
