"""
base_agent — abstract base class for all RAGBuddy AI agents.

Handles:
- Loading system prompts from the prompts/ directory
- Building OpenAI-compatible message arrays
- Exponential-backoff retry for API failures
- Shared OpenAI AsyncClient reference
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path

import openai

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, client: openai.AsyncOpenAI, model: str):
        self.client = client
        self.model = model
        self._system_prompt: str | None = None

    # ── System prompt ─────────────────────────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            prompt_file = PROMPTS_DIR / self._prompt_filename()
            if prompt_file.exists():
                self._system_prompt = prompt_file.read_text(encoding="utf-8")
            else:
                self._system_prompt = ""
        return self._system_prompt

    @abstractmethod
    def _prompt_filename(self) -> str:
        """Return the filename of the system prompt in prompts/ directory."""

    def _system_message(self) -> list[dict]:
        """Return the system prompt as an OpenAI messages-array entry."""
        return [{"role": "system", "content": self.system_prompt}]

    def _build_messages(self, user_content: str) -> list[dict]:
        """Convenience: system message + single user turn."""
        return self._system_message() + [{"role": "user", "content": user_content}]

    # ── Retry helper (non-streaming calls) ───────────────────────────────────

    async def _call_with_retry(
        self,
        coro_factory,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_delay: float | None = None,
    ):
        """
        Execute a coroutine factory with exponential backoff retry.

        coro_factory: zero-argument callable returning a FRESH coroutine each time,
        e.g. lambda: self.client.chat.completions.create(...).

        Retries on: RateLimitError, InternalServerError, APIConnectionError.
        All other exceptions propagate immediately.

        Do NOT use this for streaming calls — partial token yields cannot be
        retried. Streaming uses the SDK's built-in retry (max_retries on client).
        """
        _max = max_retries if max_retries is not None else 3
        _base = base_delay if base_delay is not None else 1.0
        _max_d = max_delay if max_delay is not None else 30.0

        last_exc: Exception | None = None
        for attempt in range(_max + 1):
            try:
                return await coro_factory()
            except (
                openai.RateLimitError,
                openai.InternalServerError,
                openai.APIConnectionError,
            ) as exc:
                last_exc = exc
                if attempt == _max:
                    break
                delay = min(_base * (2 ** attempt) + random.uniform(0, 1), _max_d)
                logger.warning(
                    "%s: API error on attempt %d/%d, retrying in %.1fs: %s",
                    self.__class__.__name__, attempt + 1, _max, delay, exc,
                )
                await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]
