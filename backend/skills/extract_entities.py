"""
extract_entities skill — extracts key entities from text using gpt-4o-mini.
Returns structured entity lists used to populate article frontmatter tags.
"""
import json

import openai

from config import settings


async def extract_entities(client: openai.AsyncOpenAI, text: str) -> dict:
    """
    Extract key entities from text.
    Returns: {topics: [], concepts: [], organizations: [], people: []}
    """
    prompt = (
        "Extract key entities from the following text. "
        "Return a JSON object with these exact keys: topics, concepts, organizations, people. "
        "Each value must be a list of strings. Only include clearly present entities. "
        "Return ONLY valid JSON, no markdown fences.\n\n"
        f"Text:\n{text[:3000]}"
    )

    response = await client.chat.completions.create(
        model=settings.skills_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    raw = (response.choices[0].message.content or "{}").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    return {
        "topics": data.get("topics", []),
        "concepts": data.get("concepts", []),
        "organizations": data.get("organizations", []),
        "people": data.get("people", []),
    }
