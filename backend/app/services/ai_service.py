"""AI provider interface, status, and JSON handling.

Rules this module enforces:
* No key -> demo mode. Nothing here ever fakes an AI answer.
* Model output is TEXT until it has been parsed AND validated by the caller.
* Errors carry a stable ``code`` and a safe, user-facing message. They never
  contain the API key, request body, or document text.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings


class AINotConfiguredError(RuntimeError):
    """Raised when code needs the AI model but no API key is set."""


class AIProviderError(RuntimeError):
    """The AI service failed (network, quota, blocked, truncated, ...)."""

    def __init__(self, code: str, message: str, retryable: bool = False, *,
                 retry_after: float | None = None, http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after
        self.http_status = http_status


class MalformedAIResponse(ValueError):
    """The model replied, but not with usable JSON."""


class AIProvider(Protocol):
    name: str
    model: str

    def generate_json(self, system: str, user: str) -> str:
        """Return the model's raw text reply (expected to be a JSON object)."""


@dataclass(frozen=True)
class AIStatus:
    mode: str  # "demo" or "live"
    provider: str
    model: str
    configured: bool
    message: str


def get_ai_status(settings: Settings) -> AIStatus:
    if settings.gemini_api_key:
        return AIStatus(
            mode="live", provider=settings.ai_provider, model=settings.gemini_model, configured=True,
            message=("AI extraction is on. Notice text is sent to the AI provider to be analysed. "
                     "Every extracted quote is checked against the document before it is marked verified."))
    return AIStatus(
        mode="demo", provider=settings.ai_provider, model=settings.gemini_model, configured=False,
        message=("Demo mode: no GEMINI_API_KEY is set. PDF text extraction and date detection work, and the "
                 "fictional demo journey is available. AI-based understanding is switched off."))


def require_ai(settings: Settings) -> None:
    if not settings.gemini_api_key:
        raise AINotConfiguredError(
            "AI features need GEMINI_API_KEY in backend/.env. The app is running in demo mode.")


def get_provider(settings: Settings) -> AIProvider:
    require_ai(settings)
    if settings.ai_provider == "gemini":
        from app.services.gemini_provider import GeminiProvider
        return GeminiProvider(settings.gemini_api_key or "", settings.gemini_model,
                              timeout=settings.ai_timeout_seconds)
    raise AIProviderError("unsupported_provider",
                          f"AI_PROVIDER '{settings.ai_provider}' is not supported. Use 'gemini'.")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_text(text: str) -> dict:
    """Turn a model reply into a dict. Tolerates ```json fences and chatter around the object."""
    cleaned = _FENCE.sub("", (text or "").strip()).strip()
    if not cleaned.startswith("{"):
        first, last = cleaned.find("{"), cleaned.rfind("}")
        if first == -1 or last <= first:
            raise MalformedAIResponse("The AI reply did not contain a JSON object.")
        cleaned = cleaned[first:last + 1]
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MalformedAIResponse(f"The AI reply was not valid JSON (at character {exc.pos}).") from None
    if not isinstance(value, dict):
        raise MalformedAIResponse("The AI reply was JSON but not an object.")
    return value
