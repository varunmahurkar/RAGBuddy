"""
synthesis_agent — streams a grounded answer from KB articles.

Uses gpt-4o-mini by default (configurable). Streaming via OpenAI's
chat.completions.create(stream=True).

Upgrade to gpt-4o for higher answer quality:  SYNTHESIS_MODEL=gpt-4o in .env

Streaming note: the streaming call relies on SDK-level retry (max_retries on
AsyncOpenAI client). Partial token yields cannot be retried safely once
streaming has begun.
"""
import logging
from collections.abc import AsyncGenerator
from typing import Any

import openai

from agents.base_agent import BaseAgent
from tools.bm25_search_tool import SearchResult

logger = logging.getLogger(__name__)


class SynthesisAgent(BaseAgent):
    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str = "gpt-4o-mini",
    ):
        super().__init__(client, model=model)

    def _prompt_filename(self) -> str:
        return "synthesis_system.txt"

    async def stream_answer(
        self,
        question: str,
        articles: list[SearchResult],
    ) -> AsyncGenerator[str, None]:
        """
        Stream an answer token-by-token as text chunks.
        Yields raw text strings — the caller assembles them into SSE events.
        """
        article_block = self._build_article_block(articles)

        # Build messages: system + article context + question
        messages: list[dict[str, Any]] = self._system_message() + [
            {
                "role": "user",
                "content": f"{article_block}\n\nQuestion: {question}",
            }
        ]

        stream = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _build_article_block(self, articles: list[SearchResult]) -> str:
        if not articles:
            return "No articles found in the knowledge base for this question."

        parts = ["Here are the relevant knowledge base articles:\n"]
        for i, article in enumerate(articles, start=1):
            parts.append(f"---\n**Article {i}: {article.article_path}**\n")
            parts.append(article.content or article.snippet or "(empty)")
            parts.append("")
        return "\n".join(parts)
