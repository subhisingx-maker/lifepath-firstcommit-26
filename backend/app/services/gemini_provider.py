"""Gemini REST client. The API key goes in a request header, never in the URL, and is never logged."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import re
import time
from typing import Callable, Optional
from urllib.parse import quote as urlquote

from app.services.ai_service import AIProviderError

Post = Callable[[str, dict, dict, float], tuple]
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 8.0


def _httpx_post(url: str, headers: dict, body: dict, timeout: float) -> tuple[int, Optional[dict], dict]:
    import httpx
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.TimeoutException:
        raise AIProviderError(
            "timeout", f"The AI service did not answer within {int(timeout)} seconds. Try again, or raise "
                       "AI_TIMEOUT_SECONDS in backend/.env.", True) from None
    except httpx.HTTPError:
        raise AIProviderError("network", "Could not reach the AI service. Check your internet connection.",
                              True) from None
    try:
        data = response.json()
    except ValueError:
        data = None
    return response.status_code, data, dict(response.headers)


_STATUS_MESSAGES = {
    400: ("bad_request", "The AI service rejected the request. Check GEMINI_API_KEY and GEMINI_MODEL.", False),
    401: ("auth", "The AI service rejected the API key. Check GEMINI_API_KEY in backend/.env.", False),
    403: ("auth", "The AI service rejected the API key. Check GEMINI_API_KEY in backend/.env.", False),
    404: ("model_not_found", "The AI model was not found. Check GEMINI_MODEL in backend/.env.", False),
    429: ("rate_limited", "The AI service quota or rate limit was reached.", True),
    503: ("service_error", "The AI service is temporarily overloaded.", True),
}


def _retry_after(headers: dict) -> Optional[float]:
    """Read either Retry-After seconds or an HTTP date; ignore malformed values."""
    raw = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        try:
            when = parsedate_to_datetime(str(raw))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _provider_detail(data: Optional[dict], api_key: str) -> str:
    """Keep useful provider diagnostics while excluding credentials and long response bodies."""
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    message = message.replace(api_key, "[redacted]") if api_key else message
    message = re.sub(r"[\r\n\t]+", " ", message).strip()
    return message[:240]


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float = 60, post: Optional[Post] = None,
                 *, sleeper: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 jitter: Callable[[float, float], float] = random.uniform) -> None:
        self._api_key = api_key          # private; never included in errors or repr
        self.model = model
        self._timeout = timeout
        self._post: Post = post or _httpx_post
        self._sleep, self._clock, self._jitter = sleeper, clock, jitter

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model!r})"

    def generate_json(self, system: str, user: str) -> str:
        url = f"{BASE}{urlquote(self.model, safe='')}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "maxOutputTokens": 8192},
        }
        deadline = self._clock() + self._timeout
        for attempt in range(MAX_ATTEMPTS):
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise AIProviderError("timeout", f"The AI request exceeded its {int(self._timeout)} second deadline. "
                                      "Try again or adjust AI_TIMEOUT_SECONDS.", True)
            try:
                result = self._post(url, headers, body, remaining)
            except AIProviderError as exc:
                # Request timeouts are handled by the extraction layer, which may split a batch.
                # Retrying them here would multiply waits across layers.
                if exc.code != "network" or attempt + 1 >= MAX_ATTEMPTS:
                    raise
                delay = self._jitter(0.0, min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2**attempt))
                if delay >= deadline - self._clock():
                    raise
                self._sleep(delay)
                continue
            status, data = result[0], result[1]
            response_headers = result[2] if len(result) > 2 and isinstance(result[2], dict) else {}
            if status == 200:
                return self._text_from(data)
            code, base_message, retry = _STATUS_MESSAGES.get(
                status, ("service_error", "The AI service is unavailable right now.", status >= 500))
            detail = _provider_detail(data, self._api_key)
            message = f"{base_message} (HTTP {status})" + (f" Provider detail: {detail}" if detail else "")
            retry_after = _retry_after(response_headers)
            error = AIProviderError(code, message, retry, retry_after=retry_after, http_status=status)
            if not retry or attempt + 1 >= MAX_ATTEMPTS:
                raise error
            ceiling = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2**attempt)
            delay = retry_after if retry_after is not None else self._jitter(0.0, ceiling)
            remaining = deadline - self._clock()
            if delay >= remaining:
                raise error
            self._sleep(delay)
        raise AIProviderError("timeout", "The AI request exceeded its overall deadline.", True)

    @staticmethod
    def _text_from(data: Optional[dict]) -> str:
        if not isinstance(data, dict):
            raise AIProviderError("bad_response", "The AI service returned an unreadable response.", True)
        candidates = data.get("candidates") or []
        if not candidates:
            if (data.get("promptFeedback") or {}).get("blockReason"):
                raise AIProviderError("blocked", "The AI service declined to process this document.")
            raise AIProviderError("empty", "The AI service returned no answer.", True)
        candidate = candidates[0] or {}
        finish = candidate.get("finishReason")
        if finish == "MAX_TOKENS":
            raise AIProviderError(
                "truncated", "The AI answer was cut off because the document section was too large.", True)
        if finish not in (None, "STOP"):
            raise AIProviderError("blocked", "The AI service stopped before finishing (safety filter).")
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if not text.strip():
            raise AIProviderError("empty", "The AI service returned an empty answer.", True)
        return text
