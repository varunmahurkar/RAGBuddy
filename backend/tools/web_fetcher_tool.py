"""
web_fetcher_tool — fetches and cleans text content from a URL.
Used for URL-based document ingestion.
"""
import logging
import re

import httpx

logger = logging.getLogger(__name__)


async def fetch_url(url: str, timeout: float = 30.0) -> str:
    """
    Fetch a URL and return cleaned plain text.
    Strips HTML tags using a simple regex approach.
    """
    headers = {
        "User-Agent": "RAGBuddy/1.0 (document ingestion bot)",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url, headers=headers)
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            return _extract_html_text(response.text, url)
        else:
            return response.text


def _extract_html_text(html: str, url: str) -> str:
    """Basic HTML text extraction — removes tags and cleans whitespace."""
    # Remove script and style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
