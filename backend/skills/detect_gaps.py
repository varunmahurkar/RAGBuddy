"""
detect_gaps skill — identifies KB gaps after a question is answered.
Used by SuggestionAgent to generate betterment suggestions.
"""
import json

import openai

from config import settings


async def detect_gaps(
    client: openai.AsyncOpenAI,
    question: str,
    answer: str,
    articles_used: list[str],
) -> list[dict]:
    """
    Analyze a Q&A pair and identify knowledge gaps.
    Returns list of {type, description, priority} dicts (max 5).
    Types: missing_topic | expand_article | update_stale | add_example
    """
    articles_str = "\n".join(f"- {a}" for a in articles_used) or "(none)"

    prompt = f"""You are a knowledge base curator analyzing gaps after answering a user question.

Question asked: {question}

Answer provided (excerpt): {answer[:1500]}

Articles used from KB:
{articles_str}

Identify specific improvements for the knowledge base. Return a JSON object with a
"suggestions" key containing an array of objects:
{{
  "suggestions": [
    {{
      "type": "missing_topic | expand_article | update_stale | add_example",
      "description": "specific, actionable description",
      "priority": "high | medium | low"
    }}
  ]
}}

Focus on concrete, actionable suggestions. Maximum 5 suggestions.
Return ONLY valid JSON."""

    response = await client.chat.completions.create(
        model=settings.skills_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    raw = (response.choices[0].message.content or "{}").strip()

    try:
        data = json.loads(raw)
        # Handle both {"suggestions": [...]} and plain [...]
        if isinstance(data, dict):
            suggestions = data.get("suggestions", data.get("items", []))
        elif isinstance(data, list):
            suggestions = data
        else:
            return []
        return suggestions[:5] if isinstance(suggestions, list) else []
    except json.JSONDecodeError:
        return []
