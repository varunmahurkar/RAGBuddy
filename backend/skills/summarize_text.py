"""
summarize_text skill — condenses long text using gpt-4o-mini.
"""
import openai

from config import settings


async def summarize(client: openai.AsyncOpenAI, text: str, max_words: int = 300) -> str:
    """Return a concise summary of the given text."""
    response = await client.chat.completions.create(
        model=settings.skills_model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize the following text in under {max_words} words. "
                    f"Preserve key facts, concepts, and important details.\n\n{text}"
                ),
            }
        ],
    )
    return (response.choices[0].message.content or "").strip()
