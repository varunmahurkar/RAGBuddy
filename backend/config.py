from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── AI provider ───────────────────────────────────────────────────────────
    openai_api_key: str

    # Per-agent model assignments (overridable via .env)
    #
    # gpt-4o-mini  — fast, cheap, strong for structured tasks (~$0.15/$0.60 per 1M tokens)
    # gpt-4o       — best quality for user-facing answers (~$2.50/$10 per 1M tokens)
    # gpt-4.1-mini — alternative cheap option (~$0.40/$1.60 per 1M tokens)
    # gpt-4.1-nano — ultra cheap for classification (~$0.10/$0.40 per 1M tokens)
    #
    # StructuringAgent: background task → cheap is fine
    structuring_model: str = "gpt-4o-mini"
    # SynthesisAgent: user-facing streaming answer → gpt-4o for quality, mini for cost
    synthesis_model: str = "gpt-4o-mini"
    # SuggestionAgent: classification/extraction → cheapest option
    suggestion_model: str = "gpt-4o-mini"
    # Skills (categorize, summarize, extract, detect_gaps): all lightweight tasks
    skills_model: str = "gpt-4o-mini"

    # Retry config
    api_max_retries: int = 3
    api_retry_base_delay: float = 1.0   # seconds
    api_retry_max_delay: float = 30.0   # seconds

    # Parallel ingestion
    max_parallel_ingestions: int = 3

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./ragbuddy.db"

    # ── Storage ───────────────────────────────────────────────────────────────
    kb_storage_path: str = "../kb_storage"
    upload_dir: str = "./uploads"

    # ── Retrieval ─────────────────────────────────────────────────────────────
    bm25_top_k: int = 10
    semantic_rerank_enabled: bool = False

    # ── Upload ────────────────────────────────────────────────────────────────
    max_upload_size_mb: int = 50

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:5173"]

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @property
    def kb_path(self) -> Path:
        return Path(self.kb_storage_path).resolve()

    @property
    def uploads_path(self) -> Path:
        return Path(self.upload_dir).resolve()


settings = Settings()
