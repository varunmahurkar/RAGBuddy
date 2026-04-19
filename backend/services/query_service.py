"""
query_service — orchestrates the question → streaming answer → suggestions pipeline.

Yields SSE-compatible event dicts that the API layer serialises to text/event-stream.

Event sequence:
  {"type": "status",      "message": "..."}
  {"type": "articles",    "data": [...]}          # retrieved articles list
  {"type": "token",       "text": "..."}           # streamed answer chunk
  {"type": "suggestions", "data": [...]}
  {"type": "done",        "latency_ms": N}
"""
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import openai

from agents.retrieval_agent import RetrievalAgent
from agents.suggestion_agent import Suggestion, SuggestionAgent
from agents.synthesis_agent import SynthesisAgent
from tools.bm25_search_tool import SearchResult

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(
        self,
        client: openai.AsyncOpenAI,
        semantic_rerank_enabled: bool = False,
        synthesis_model: str = "gpt-4o-mini",
        suggestion_model: str = "gpt-4o-mini",
    ):
        self._retrieval = RetrievalAgent(client, semantic_rerank_enabled=semantic_rerank_enabled)
        self._synthesis = SynthesisAgent(client, model=synthesis_model)
        self._suggestion = SuggestionAgent(client, model=suggestion_model)

    async def stream(
        self, question: str, max_articles: int = 5
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Full pipeline as an async generator of SSE event dicts."""
        start = time.monotonic()
        full_answer = ""
        articles: list[SearchResult] = []
        suggestions: list[Suggestion] = []

        # ── Retrieval ────────────────────────────────────────────────────────
        yield {"type": "status", "message": "Searching knowledge base…"}
        try:
            articles = await self._retrieval.retrieve(question, max_articles=max_articles)
        except Exception as exc:
            logger.error("Retrieval failed: %s", exc)
            yield {"type": "status", "message": "Retrieval error — answering without KB context."}

        yield {
            "type": "articles",
            "data": [
                {"path": a.article_path, "score": round(a.score, 4), "snippet": a.snippet}
                for a in articles
            ],
        }

        # ── Synthesis (streaming) ─────────────────────────────────────────────
        yield {"type": "status", "message": "Generating answer…"}
        try:
            async for chunk in self._synthesis.stream_answer(question, articles):
                full_answer += chunk
                yield {"type": "token", "text": chunk}
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            error_msg = "\n\n*(Error generating answer — please try again.)*"
            full_answer += error_msg
            yield {"type": "token", "text": error_msg}

        # ── Suggestions ───────────────────────────────────────────────────────
        yield {"type": "status", "message": "Analysing knowledge gaps…"}
        try:
            suggestions = await self._suggestion.suggest(question, full_answer, articles)
        except Exception as exc:
            logger.warning("Suggestion agent failed: %s", exc)

        yield {
            "type": "suggestions",
            "data": [
                {"type": s.type, "description": s.description, "priority": s.priority}
                for s in suggestions
            ],
        }

        # ── Persist to history ────────────────────────────────────────────────
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            from db.database import AsyncSessionLocal
            from db.repositories import QueryRepository

            async with AsyncSessionLocal() as session:
                query_repo = QueryRepository(session)
                await query_repo.create(
                    question=question,
                    answer=full_answer,
                    articles_used=[a.article_path for a in articles],
                    suggestions=[
                        {"type": s.type, "description": s.description, "priority": s.priority}
                        for s in suggestions
                    ],
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            logger.warning("Failed to save query history: %s", exc)

        yield {"type": "done", "latency_ms": latency_ms}
