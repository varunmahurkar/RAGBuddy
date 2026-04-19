from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = "sqlite" in settings.database_url

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # SQLite: prevent "check same thread" error in async context
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # SQLite: allow only one writer at a time but many concurrent readers
    # (WAL mode set via pragma below)
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _apply_sqlite_pragmas(conn, _):
    """
    Apply performance pragmas to each new SQLite connection.

    WAL (Write-Ahead Logging) mode:
      - Readers never block writers; writers never block readers
      - Much faster for the RAGBuddy workload (many concurrent reads, few writes)

    synchronous = NORMAL:
      - Safe for WAL mode; avoids fsync on every write (big speed boost)

    cache_size = -64000:
      - 64 MB page cache per connection; keeps hot articles in memory

    foreign_keys = ON:
      - Enforce referential integrity (good practice)
    """
    await conn.execute(text("PRAGMA journal_mode=WAL"))
    await conn.execute(text("PRAGMA synchronous=NORMAL"))
    await conn.execute(text("PRAGMA cache_size=-64000"))   # 64 MB
    await conn.execute(text("PRAGMA temp_store=MEMORY"))
    await conn.execute(text("PRAGMA mmap_size=268435456")) # 256 MB memory-mapped I/O
    await conn.execute(text("PRAGMA foreign_keys=ON"))


if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        """Sync fallback for the connect event (required for SQLAlchemy event system)."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def init_db():
    async with engine.begin() as conn:
        from db import models  # noqa: F401 — import to register all models
        await conn.run_sync(Base.metadata.create_all)

        # Run ANALYZE after schema creation so SQLite's query planner
        # has statistics for the new indexes
        if _is_sqlite:
            await conn.execute(text("PRAGMA optimize"))


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
