from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Index, Integer, String, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Existing tables ────────────────────────────────────────────────────────────

class IngestionHistory(Base):
    __tablename__ = "ingestion_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Status: pending | processing | completed | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    articles_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    articles_used: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    suggestions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KBVersions(Base):
    __tablename__ = "kb_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # created | updated | deleted
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── New tables ─────────────────────────────────────────────────────────────────

class KBArticle(Base):
    """
    Mirror of every KB article stored in SQLite.

    Disk .md files remain the canonical human-readable format (good for git /
    editors). This table is the operational read store — all API list/search/
    read calls hit SQLite (indexed, sub-millisecond) instead of scanning the
    filesystem.

    Populated by kb_writer_tool.write_article() on every create/update.
    Rebuilt from disk on startup if empty (zero articles in DB but files exist).
    """
    __tablename__ = "kb_articles"
    __table_args__ = (
        UniqueConstraint("relative_path", name="uq_kb_article_path"),
        Index("ix_kb_article_category", "category"),
        Index("ix_kb_article_updated", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(512), nullable=False)
    # Relative path within kb_storage, e.g. "Science/AI/ml.md"
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    # JSON list of tag strings
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # JSON list of source filenames
    sources: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Full markdown content (no frontmatter) — served directly from DB, no disk read
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # First ~300 chars for list views
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Document(Base):
    """
    Tracks every uploaded source document.

    Previously only tracked on the filesystem — now stored in SQLite so the
    document list is a fast indexed query rather than a directory scan.
    """
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("filename", name="uq_document_filename"),
        Index("ix_document_uploaded_at", "uploaded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    # Absolute path to the upload on disk
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
