"""
document_service — manages uploaded files.

Files are saved to the uploads directory on disk.
Metadata is also stored in SQLite (Document table) so listings
are fast indexed queries instead of directory scans.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class DocumentService:
    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, filename: str, data: bytes) -> Path:
        """
        Persist uploaded bytes to disk and record the file in SQLite.
        Returns the saved path.
        """
        dest = self.upload_dir / filename
        dest.write_bytes(data)
        logger.info("Saved upload: %s (%d bytes)", dest, len(data))

        # Record in SQLite
        try:
            from db.database import AsyncSessionLocal
            from db.repositories import DocumentRepository

            async with AsyncSessionLocal() as session:
                repo = DocumentRepository(session)
                await repo.upsert(
                    filename=filename,
                    size_bytes=len(data),
                    extension=Path(filename).suffix.lower(),
                    path=str(dest),
                )
        except Exception as exc:
            logger.warning("Document DB record failed for %s: %s", filename, exc)

        return dest

    async def list_uploads(self) -> list[dict]:
        """
        List uploaded documents from SQLite (fast indexed query).
        Falls back to filesystem scan if DB is unavailable.
        """
        try:
            from db.database import AsyncSessionLocal
            from db.repositories import DocumentRepository

            async with AsyncSessionLocal() as session:
                repo = DocumentRepository(session)
                docs = await repo.list_all()
                return [
                    {
                        "name": d.filename,
                        "size": d.size_bytes,
                        "extension": d.extension,
                        "path": d.path,
                        "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                    }
                    for d in docs
                ]
        except Exception as exc:
            logger.warning("DB document list failed, falling back to filesystem: %s", exc)
            return self._list_from_disk()

    def _list_from_disk(self) -> list[dict]:
        """Filesystem fallback for document listing."""
        files = []
        for p in sorted(self.upload_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append(
                    {
                        "name": p.name,
                        "size": p.stat().st_size,
                        "extension": p.suffix.lower(),
                        "path": str(p),
                        "uploaded_at": None,
                    }
                )
        return files

    async def delete_upload(self, filename: str) -> bool:
        target = self.upload_dir / filename
        deleted = False
        if target.exists() and target.is_file():
            target.unlink()
            deleted = True

        try:
            from db.database import AsyncSessionLocal
            from db.repositories import DocumentRepository

            async with AsyncSessionLocal() as session:
                repo = DocumentRepository(session)
                await repo.delete_by_filename(filename)
        except Exception as exc:
            logger.warning("Document DB delete failed for %s: %s", filename, exc)

        return deleted

    @staticmethod
    def is_allowed(filename: str) -> bool:
        return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS
