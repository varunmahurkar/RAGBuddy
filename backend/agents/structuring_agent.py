"""
structuring_agent — converts raw document text into Wikipedia-style KB articles.

Uses gpt-4o-mini by default (configurable). JSON structured output via
response_format={"type": "json_object"}.

Default model: gpt-4o-mini (cheap, fast, excellent at structured JSON output).
Override via STRUCTURING_MODEL in .env.
"""
import json
import logging
from typing import Any

import openai

from agents.base_agent import BaseAgent
from kb.repository import ArticleData
from skills.generate_frontmatter import generate_frontmatter

logger = logging.getLogger(__name__)


class StructuringAgent(BaseAgent):
    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str = "gpt-4o-mini",
    ):
        super().__init__(client, model=model)

    def _prompt_filename(self) -> str:
        return "structuring_system.txt"

    async def structure_document(
        self,
        text: str,
        source_name: str,
        existing_categories: list[str],
        existing_titles: list[str],
    ) -> list[ArticleData]:
        """
        Convert raw document text into one or more KB articles.

        Returns a list of ArticleData objects ready to be written to the KB.
        """
        categories_block = (
            "\n".join(f"- {c}" for c in existing_categories)
            if existing_categories
            else "(none yet — create new categories as needed)"
        )
        titles_block = (
            "\n".join(f"- {t}" for t in existing_titles[:50])
            if existing_titles
            else "(none yet)"
        )

        user_content = f"""Existing KB categories (prefer reusing these):
{categories_block}

Existing article titles (avoid exact duplicates):
{titles_block}

Document source: {source_name}

Document content:
{text}"""

        response = await self._call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.model,
                max_tokens=8192,
                messages=self._build_messages(user_content),
                # Forces the model to emit valid JSON. The system prompt already
                # instructs JSON-only output — this makes it a hard guarantee.
                response_format={"type": "json_object"},
            )
        )

        raw_json = response.choices[0].message.content or "[]"
        return self._parse_response(raw_json, source_name)

    def _parse_response(self, raw_json: str, source_name: str) -> list[ArticleData]:
        try:
            data = json.loads(raw_json)
            # The system prompt returns a JSON array; some models wrap it in
            # {"articles": [...]} — handle both shapes.
            if isinstance(data, dict):
                items = data.get("articles", data.get("items", [data]))
            elif isinstance(data, list):
                items = data
            else:
                logger.error("StructuringAgent: unexpected JSON shape: %s", type(data))
                return []
        except json.JSONDecodeError as exc:
            logger.error("StructuringAgent: JSON parse error: %s", exc)
            return []

        articles: list[ArticleData] = []
        for item in items:
            try:
                title = item.get("title", "Untitled")
                category = item.get("category", "Uncategorized")
                tags = item.get("tags", [])
                content_body = item.get("content", "")

                frontmatter = generate_frontmatter(
                    title=title,
                    category=category,
                    tags=tags,
                    sources=[source_name],
                )

                articles.append(
                    ArticleData(
                        title=title,
                        category=category,
                        tags=tags,
                        content=content_body,
                        sources=[source_name],
                        version=frontmatter.get("version", 1),
                    )
                )
            except Exception as exc:
                logger.warning("StructuringAgent: skipping malformed item: %s", exc)

        return articles
