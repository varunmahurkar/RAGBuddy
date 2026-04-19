"""
ingestion_service — orchestrates the document → KB pipeline.

Pipeline:
  1. Read raw text from file (file_reader_tool)
  2. Structure text into articles (StructuringAgent → gpt-4o-mini)
  3. Write articles to disk + SQLite + BM25 index (kb_writer_tool)
  4. Record ingestion history in DB

Supports parallel ingestion of multiple files via ingest_many(),
bounded by an asyncio.Semaphore to prevent API rate limit exhaustion.
"""
import asyncio
import logging
from pathlib import Path

import openai

from agents.structuring_agent import StructuringAgent
from kb.repository import AbstractKBRepository
from tools.file_reader_tool import read_file
from tools.kb_writer_tool import write_article

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        client: openai.AsyncOpenAI,
        kb_repo: AbstractKBRepository,
        structuring_model: str = "gpt-4o-mini",
        max_parallel: int = 3,
    ):
        self._agent = StructuringAgent(client, model=structuring_model)
        self._kb_repo = kb_repo
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def ingest(self, file_path: Path, ingestion_id: int) -> int:
        """Run ingestion for a single file, bounded by semaphore."""
        async with self._semaphore:
            return await self._ingest_inner(file_path, ingestion_id)

    async def _ingest_inner(self, file_path: Path, ingestion_id: int) -> int:
        from db.database import AsyncSessionLocal
        from db.repositories import IngestionRepository

        source_name = file_path.name

        async def _update_status(status: str, **kwargs):
            async with AsyncSessionLocal() as session:
                repo = IngestionRepository(session)
                await repo.update_status(ingestion_id, status, **kwargs)

        await _update_status("processing")

        try:
            text = read_file(file_path)
            if not text.strip():
                raise ValueError(f"No extractable text in {source_name}")

            existing_articles = self._kb_repo.list_articles()
            existing_categories = list({a.category for a in existing_articles})
            existing_titles = [a.title for a in existing_articles]

            articles = await self._agent.structure_document(
                text=text,
                source_name=source_name,
                existing_categories=existing_categories,
                existing_titles=existing_titles,
            )

            if not articles:
                raise ValueError("StructuringAgent returned no articles")

            count = 0
            for article in articles:
                await write_article(article)
                count += 1

            await _update_status("completed", articles_created=count)
            logger.info(
                "Ingestion %d complete: %d articles from %s (model: %s)",
                ingestion_id, count, source_name, self._agent.model,
            )
            return count

        except Exception as exc:
            logger.error("Ingestion %d failed: %s", ingestion_id, exc, exc_info=True)
            await _update_status("failed", error_message=str(exc))
            raise

    async def ingest_many(self, files: list[tuple[Path, int]]) -> list[int]:
        """Run ingestion for multiple files in parallel (bounded by semaphore)."""
        tasks = [
            asyncio.create_task(self.ingest(fp, iid))
            for fp, iid in files
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        counts: list[int] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Batch ingestion failed for %s: %s", files[i][0].name, result)
                counts.append(0)
            else:
                counts.append(result)  # type: ignore[arg-type]
        return counts
