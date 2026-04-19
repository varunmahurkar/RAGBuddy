"""
suggestion_agent — identifies KB gaps after answering a question.

Uses gpt-4o-mini by default (configurable). Classification task — cheap model
is the right call. Override via SUGGESTION_MODEL in .env.
"""
import json
import logging
from dataclasses import dataclass

import openai

from agents.base_agent import BaseAgent
from tools.bm25_search_tool import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    type: str          # missing_topic | expand_article | update_stale | add_example
    description: str
    priority: str      # high | medium | low


class SuggestionAgent(BaseAgent):
    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str = "gpt-4o-mini",
    ):
        super().__init__(client, model=model)

    def _prompt_filename(self) -> str:
        return "suggestion_system.txt"

    async def suggest(
        self,
        question: str,
        answer: str,
        articles_used: list[SearchResult],
    ) -> list[Suggestion]:
        """
        Analyse question + answer + articles to surface KB improvement suggestions.
        Returns a list of Suggestion objects (max 5).
        """
        articles_summary = self._summarize_articles(articles_used)

        user_content = f"""User question: {question}

Answer provided:
{answer}

Articles used from the knowledge base:
{articles_summary}

Identify gaps and suggest concrete improvements to the knowledge base."""

        response = await self._call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=self._build_messages(user_content),
                response_format={"type": "json_object"},
            )
        )

        raw = response.choices[0].message.content or "[]"
        return self._parse_suggestions(raw)

    def _summarize_articles(self, articles: list[SearchResult]) -> str:
        if not articles:
            return "(no articles retrieved — question answered without KB support)"
        return "\n".join(f"- {a.article_path} (score: {a.score:.3f})" for a in articles)

    def _parse_suggestions(self, raw: str) -> list[Suggestion]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
            # Handle both {"suggestions": [...]} and plain [...]
            if isinstance(data, dict):
                items = data.get("suggestions", data.get("items", []))
            elif isinstance(data, list):
                items = data
            else:
                return []
        except json.JSONDecodeError as exc:
            logger.warning("SuggestionAgent: JSON parse error: %s\nRaw: %s", exc, raw[:300])
            return []

        suggestions = []
        for item in items[:5]:
            try:
                suggestions.append(
                    Suggestion(
                        type=item.get("type", "missing_topic"),
                        description=item.get("description", ""),
                        priority=item.get("priority", "medium"),
                    )
                )
            except Exception:
                continue
        return suggestions
