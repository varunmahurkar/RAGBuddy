"""
categorize_content skill — classifies text into a KB category path using gpt-4o-mini.
Prefers existing categories to keep the KB coherent.
"""
import openai

from config import settings


async def categorize(
    client: openai.AsyncOpenAI,
    text: str,
    title: str,
    existing_categories: list[str],
) -> str:
    """
    Return a category path like "Computer Science/AI" for the given text.
    Prefers reusing existing_categories when appropriate.
    """
    existing_str = "\n".join(f"- {c}" for c in existing_categories[:50]) or "(none yet)"

    prompt = f"""You are organizing documents into a Wikipedia-like knowledge base.

Existing categories:
{existing_str}

Document title: {title}
Document excerpt:
{text[:2000]}

Choose or create the best category path for this document.
- Prefer existing categories when the content fits
- Use 1-3 levels (e.g. "Science", "Science/Biology", "Science/Biology/Genetics")
- Be concise and consistent

Return ONLY the category path as a plain string, no explanation, no markdown."""

    response = await client.chat.completions.create(
        model=settings.skills_model,
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )

    category = (response.choices[0].message.content or "General").strip().strip('"').strip("'")
    category = "/".join(p.strip() for p in category.split("/") if p.strip())
    return category or "General"
