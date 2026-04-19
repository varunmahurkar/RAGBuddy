"""
bm25_search_tool — BM25 keyword search over the KB index.

The IndexManager singleton is injected at startup via set_index_manager().
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_index_manager = None


def set_index_manager(im) -> None:
    global _index_manager
    _index_manager = im


@dataclass
class SearchResult:
    article_path: str        # relative path within kb_storage (e.g. "Science/AI/ml.md")
    score: float
    snippet: str = ""
    content: str = ""        # full article content, populated when available


def search(query: str, top_k: int = 10) -> list[SearchResult]:
    """
    Run BM25 search over all KB articles.
    Returns list of SearchResult sorted by relevance descending.
    """
    if _index_manager is None:
        logger.warning("BM25 index not initialized — returning empty results.")
        return []

    raw = _index_manager.search(query, top_k=top_k)
    results = []
    for path, score, content in raw:
        snippet = content[:300].replace("\n", " ") if content else ""
        results.append(SearchResult(article_path=path, score=score, snippet=snippet, content=content))
    return results


def get_article_by_path(article_path: str) -> SearchResult | None:
    """
    Fetch a single article by its relative path from the index.
    Returns None if not found.
    """
    if _index_manager is None:
        return None
    result = _index_manager.get_by_path(article_path)
    if result is None:
        return None
    path, content = result
    snippet = content[:300].replace("\n", " ") if content else ""
    return SearchResult(article_path=path, score=0.0, snippet=snippet, content=content)
