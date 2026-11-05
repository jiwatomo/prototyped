"""Application configuration loaded from environment variables / backend/.env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
ENV_PATH = BASE_DIR / ".env"


def _load_env_file(path: Path) -> None:
    """Minimal .env loader (no external dependency). Existing env vars win."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


class Settings(BaseModel):
    ai_provider: str = "auto"
    ai_fallback_enabled: bool = True
    ai_api_format: str = "openai_compatible"
    ai_api_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_chat_completions_path: str = "/chat/completions"
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 1
    ai_temperature: float = 0.1
    ai_max_input_chars: int = 30000

    database_url: str = ""
    max_pdf_bytes: int = 5_000_000
    session_ttl_minutes: int = 480
    cors_origins: list[str] = [
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ]

    @property
    def llm_configured(self) -> bool:
        return bool(self.ai_api_base_url and self.ai_api_key and self.ai_model)

    @property
    def resolved_provider_mode(self) -> str:
        """Which provider the factory will actually use: 'llm' or 'mock'."""
        mode = self.ai_provider.strip().lower()
        if mode == "mock":
            return "mock"
        if mode == "llm":
            if self.llm_configured:
                return "llm"
            return "mock"  # only reachable when fallback is enabled
        # auto
        return "llm" if self.llm_configured else "mock"


@lru_cache
def get_settings() -> Settings:
    _load_env_file(ENV_PATH)
    db_path = (BASE_DIR / "app.db").as_posix()
    cors = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in cors.split(",") if o.strip()] or Settings().cors_origins
    return Settings(
        ai_provider=os.environ.get("AI_PROVIDER", "auto"),
        ai_fallback_enabled=_as_bool(os.environ.get("AI_FALLBACK_ENABLED"), True),
        ai_api_format=os.environ.get("AI_API_FORMAT", "openai_compatible"),
        ai_api_base_url=os.environ.get("AI_API_BASE_URL", ""),
        ai_api_key=os.environ.get("AI_API_KEY", ""),
        ai_model=os.environ.get("AI_MODEL", ""),
        ai_chat_completions_path=os.environ.get("AI_CHAT_COMPLETIONS_PATH", "/chat/completions"),
        ai_timeout_seconds=_as_float(os.environ.get("AI_TIMEOUT_SECONDS"), 30.0),
        ai_max_retries=_as_int(os.environ.get("AI_MAX_RETRIES"), 1),
        ai_temperature=_as_float(os.environ.get("AI_TEMPERATURE"), 0.1),
        ai_max_input_chars=_as_int(os.environ.get("AI_MAX_INPUT_CHARS"), 30000),
        database_url=os.environ.get("DATABASE_URL", f"sqlite:///{db_path}"),
        max_pdf_bytes=_as_int(os.environ.get("MAX_PDF_BYTES"), 5_000_000),
        session_ttl_minutes=_as_int(os.environ.get("SESSION_TTL_MINUTES"), 480),
        cors_origins=origins,
    )


settings = get_settings()
