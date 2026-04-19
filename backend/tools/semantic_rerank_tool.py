"""
semantic_rerank_tool — optional fastembed-based semantic re-ranking.

Only active when SEMANTIC_RERANK_ENABLED=true and fastembed is installed.
Falls back gracefully if fastembed is not available.
"""
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tools.bm25_search_tool import SearchResult

_embeddings = None
_model_loaded = False


def _load_model():
    global _embeddings, _model_loaded
    if _model_loaded:
        return
    try:
        from fastembed import TextEmbedding
        _embeddings = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("fastembed semantic reranking model loaded.")
    except ImportError:
        logger.warning("fastembed not installed — semantic reranking disabled.")
    _model_loaded = True


def rerank(query: str, candidates: list, top_k: int | None = None) -> list:
    """
    Re-rank BM25 search results using semantic similarity.
    Falls back to original order if fastembed is unavailable.
    """
    _load_model()
    if _embeddings is None or len(candidates) <= 1:
        return candidates[:top_k] if top_k else candidates

    try:
        import numpy as np

        # Use snippet or content for re-ranking text
        texts = [c.snippet or c.content or c.article_path for c in candidates]

        query_emb = list(_embeddings.embed([query]))[0]
        doc_embs = list(_embeddings.embed(texts))

        scores = []
        for doc_emb in doc_embs:
            score = float(np.dot(query_emb, doc_emb))
            scores.append(score)

        ranked = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        reranked = [c for c, _ in ranked]
        logger.debug("Semantic reranking applied to %d candidates.", len(candidates))
        return reranked[:top_k] if top_k else reranked
    except Exception as e:
        logger.warning(f"Semantic reranking failed: {e}")
        return candidates
