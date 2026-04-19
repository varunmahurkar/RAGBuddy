import json
import logging
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from kb.repository import AbstractKBRepository

logger = logging.getLogger(__name__)

INDEX_FILE = "_index.json"


class IndexManager:
    """
    Manages a BM25 index over all KB articles.

    The index is persisted to _index.json in the KB root so that searches
    are instant on startup without reading all files.
    """

    def __init__(self, kb_path: Path):
        self.kb_path = kb_path
        self._index_path = kb_path / INDEX_FILE
        self._corpus: list[list[str]] = []   # tokenized documents
        self._paths: list[str] = []          # parallel: article relative paths
        self._contents: list[str] = []       # parallel: full article text (for snippets)
        self._bm25: Optional[BM25Okapi] = None

    # ------------------------------------------------------------------
    # Build / load / save
    # ------------------------------------------------------------------

    def build_from_repository(self, repo: AbstractKBRepository) -> None:
        """Rebuild index from all articles in the repository."""
        articles = repo.get_all_articles_content()
        self._paths = [path for path, _ in articles]
        self._contents = [text for _, text in articles]
        self._corpus = [self._tokenize(text) for text in self._contents]
        self._rebuild_bm25()
        self._save()
        logger.info("BM25 index built: %d articles.", len(self._paths))

    def load(self) -> bool:
        """Load persisted index. Returns True if loaded successfully."""
        if not self._index_path.exists():
            return False
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._paths = data["paths"]
            self._corpus = data["corpus"]
            self._contents = data.get("contents", [""] * len(self._paths))
            self._rebuild_bm25()
            logger.info("BM25 index loaded: %d articles.", len(self._paths))
            return True
        except Exception as e:
            logger.warning("Failed to load BM25 index: %s", e)
            return False

    def _save(self) -> None:
        data = {"paths": self._paths, "corpus": self._corpus, "contents": self._contents}
        self._index_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def _rebuild_bm25(self) -> None:
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def upsert_article(self, relative_path: str, text: str) -> None:
        """Add or update a single article in the index."""
        tokens = self._tokenize(text)
        if relative_path in self._paths:
            idx = self._paths.index(relative_path)
            self._corpus[idx] = tokens
            self._contents[idx] = text
        else:
            self._paths.append(relative_path)
            self._corpus.append(tokens)
            self._contents.append(text)
        self._rebuild_bm25()
        self._save()

    def remove_article(self, relative_path: str) -> None:
        if relative_path in self._paths:
            idx = self._paths.index(relative_path)
            self._paths.pop(idx)
            self._corpus.pop(idx)
            self._contents.pop(idx)
            self._rebuild_bm25()
            self._save()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float, str]]:
        """
        Returns list of (relative_path, score, content) sorted by relevance descending.
        """
        if self._bm25 is None or not self._paths:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        ranked = sorted(
            zip(self._paths, scores, self._contents),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(path, score, content) for path, score, content in ranked[:top_k] if score > 0]

    def get_by_path(self, relative_path: str) -> tuple[str, str] | None:
        """Fetch a single article's (path, content) by relative path."""
        if relative_path in self._paths:
            idx = self._paths.index(relative_path)
            return (self._paths[idx], self._contents[idx])
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().split()

    @property
    def article_count(self) -> int:
        return len(self._paths)
