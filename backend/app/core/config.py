"""Application settings.

Values come from real environment variables first, then from ``backend/.env``.
Only the standard library is used so this file is easy to read and test.

The Gemini key is OPTIONAL. Without it the app runs in "demo" mode.
The key is never printed, logged, or returned by any API.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"

# Values people leave in .env.example that must NOT count as a real key.
_PLACEHOLDER_KEYS = {"", "your_gemini_api_key_here", "changeme", "none", "null"}

_KNOWN_KEYS = (
    "APP_ENV",
    "AI_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MAX_UPLOAD_MB",
    "MAX_PDF_PAGES",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "AI_TIMEOUT_SECONDS",
    "AI_BATCH_CHARS",
    "AI_RATE_LIMIT_PER_MINUTE",
)


def parse_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines. Missing file -> empty dict (that is fine)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    # utf-8-sig drops the invisible BOM that Windows Notepad can add.
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def _to_int(name: str, raw: str, minimum: int) -> int:
    try:
        number = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got {raw!r}") from None
    if number < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {number}")
    return number


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    ai_provider: str = "gemini"
    gemini_api_key: Optional[str] = field(default=None, repr=False)  # never shown in repr
    gemini_model: str = "gemini-3.8-flash"
    max_upload_mb: int = 10
    max_pdf_pages: int = 300
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    # SQLite file inside backend/. Change to a PostgreSQL URL later without code changes.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'lifepath.db').as_posix()}"
    ai_timeout_seconds: int = 120
    ai_batch_chars: int = 24000          # max characters of notice text per AI request
    ai_rate_limit_per_minute: int = 10   # per client, for expensive AI endpoints

    @property
    def ai_mode(self) -> str:
        """'live' only when a real key is configured; otherwise 'demo'."""
        return "live" if self.gemini_api_key else "demo"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings(
    env_file: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Settings:
    file_values = parse_env_file(DEFAULT_ENV_FILE if env_file is None else env_file)
    env = os.environ if environ is None else environ
    merged = dict(file_values)
    merged.update({k: env[k] for k in _KNOWN_KEYS if k in env})  # real env wins

    key = (merged.get("GEMINI_API_KEY") or "").strip()
    api_key = None if key.lower() in _PLACEHOLDER_KEYS else key

    origins = tuple(
        o.strip() for o in merged.get("CORS_ORIGINS", "").split(",") if o.strip()
    ) or Settings().cors_origins

    return Settings(
        app_env=merged.get("APP_ENV", "development"),
        ai_provider=merged.get("AI_PROVIDER", "gemini").strip().lower(),
        gemini_api_key=api_key,
        gemini_model=merged.get("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        max_upload_mb=_to_int("MAX_UPLOAD_MB", merged.get("MAX_UPLOAD_MB", "10"), 1),
        max_pdf_pages=_to_int("MAX_PDF_PAGES", merged.get("MAX_PDF_PAGES", "300"), 1),
        cors_origins=origins,
        database_url=merged.get("DATABASE_URL", "").strip() or Settings().database_url,
        ai_timeout_seconds=_to_int("AI_TIMEOUT_SECONDS", merged.get("AI_TIMEOUT_SECONDS", "120"), 5),
        ai_batch_chars=_to_int("AI_BATCH_CHARS", merged.get("AI_BATCH_CHARS", "24000"), 2000),
        ai_rate_limit_per_minute=_to_int(
            "AI_RATE_LIMIT_PER_MINUTE", merged.get("AI_RATE_LIMIT_PER_MINUTE", "10"), 1),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
