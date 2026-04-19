"""
retrieval_agent — retrieves relevant KB articles for a question.

Pure BM25 search (no Claude call). Optionally re-ranks with fastembed.
Expands results by following See Also links one level deep.
"""
import logging
import re

import openai

from agents.base_agent import BaseAgent
from tools.bm25_search_tool import SearchResult, search as bm25_search
from tools.semantic_rerank_tool import rerank as semantic_rerank

logger = logging.getLogger(__name__)

_SEE_ALSO_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


class RetrievalAgent(BaseAgent):
    def __init__(self, client: openai.AsyncOpenAI, semantic_rerank_enabled: bool = False):
        super().__init__(client, model="")  # No LLM calls — model unused
        self._semantic_rerank_enabled = semantic_rerank_enabled

    def _prompt_filename(self) -> str:
        # RetrievalAgent has no system prompt — it uses no Claude call.
        return "retrieval_system.txt"

    async def retrieve(
        self,
        question: str,
        max_articles: int = 5,
    ) -> list[SearchResult]:
        """
        Retrieve the most relevant articles for a question.

        Steps:
        1. BM25 search with top_k = max(max_articles * 2, 10)
        2. Optional semantic re-ranking (reduces to max_articles)
        3. See Also expansion (1 level, top max_articles articles only)

        Returns a list of SearchResult(article_path, score, snippet, content).
        """
        initial_k = max(max_articles * 2, 10)
        candidates = bm25_search(question, top_k=initial_k)

        if not candidates:
            return []

        if self._semantic_rerank_enabled and len(candidates) > max_articles:
            try:
                candidates = semantic_rerank(question, candidates, top_k=max_articles)
            except Exception as exc:
                logger.warning("Semantic rerank failed, falling back to BM25 order: %s", exc)
                candidates = candidates[:max_articles]
        else:
            candidates = candidates[:max_articles]

        expanded = await self._expand_see_also(candidates, max_articles)
        return expanded

    async def _expand_see_also(
        self,
        results: list[SearchResult],
        max_articles: int,
    ) -> list[SearchResult]:
        """Follow See Also links in top articles to discover related content."""
        from tools.bm25_search_tool import get_article_by_path

        seen_paths = {r.article_path for r in results}
        expanded = list(results)

        for result in results[:3]:  # Only expand from top-3 to limit noise
            if not result.content:
                continue
            see_also_links = _SEE_ALSO_PATTERN.findall(result.content)
            for link in see_also_links:
                if len(expanded) >= max_articles:
                    break
                # Convert [[Category/Topic]] to a path like category/topic.md
                candidate_path = link.lower().replace(" ", "_") + ".md"
                if candidate_path in seen_paths:
                    continue
                linked = get_article_by_path(candidate_path)
                if linked:
                    seen_paths.add(candidate_path)
                    expanded.append(linked)

        return expanded[:max_articles]
