"""AI-assisted extraction with deterministic checking.

Division of labour (this is the heart of LIFEPATH's honesty):
  AI           reads the notice and PROPOSES items with a quote and a page.
  This code    validates the shape, re-checks every quote against the real text,
               takes dates from the deterministic parser (never from the AI), and
               decides the status. Nothing becomes "verified" because the model said so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from pydantic import ValidationError

from app.schemas.extraction import AIItem, HeaderField
from app.services.ai_service import (AIProvider, AIProviderError, MalformedAIResponse, parse_json_text)
from app.services.deadline_parser import find_dates
from app.services.prompt_builder import (SYSTEM_PROMPT, batch_pages, build_repair_prompt, build_user_prompt)
from app.services.quote_verifier import VERIFIED, PageIndex, normalise, verify_quote

FATAL_CODES = {"auth", "model_not_found", "bad_request", "unsupported_provider"}
STOP_AFTER_PROVIDER_FAILURE = {"rate_limited", "service_error", "network"}
# "This request was too big for one answer": the AI ran out of time or out of room. Not fatal, and a
# smaller request often works, so the batch is split in half and tried again (see _analyse).
SPLITTABLE_CODES = {"timeout", "truncated"}
MAX_SPLIT_DEPTH = 1            # batch -> two halves. No further, so one bad batch cannot cost many waits.
MAX_CONSECUTIVE_SLOW = 2       # stop early after this many batches in a row that were too big even when split
MIN_BATCH_CHARS = 2000         # never shrink batches below this (same floor as AI_BATCH_CHARS)
MAX_ITEMS_PER_BATCH = 200
HEADER_FIELDS = ("institution", "programme", "academic_year")


class ExtractionFailed(Exception):
    """The AI could not produce usable output for the document."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class ReviewItem:
    category: str
    name: str
    explanation: str                 # AI wording
    supporting_quote: str            # exact words from the notice (when quote_check == verified)
    source_page: int
    quote_check: str                 # verified | needs_review | unverified
    quote_note: Optional[str] = None
    requirement_level: Optional[str] = None
    condition: Optional[str] = None
    event_key: Optional[str] = None
    outcome: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    missing_information: Optional[str] = None
    date_iso: Optional[str] = None
    date_status: Optional[str] = None
    date_reason: Optional[str] = None


@dataclass
class HeaderValue:
    value: str
    page: Optional[int]
    quote_check: str
    note: Optional[str] = None


@dataclass
class PipelineResult:
    header: dict[str, Optional[HeaderValue]]
    items: list[ReviewItem]
    not_found: list[str]
    warnings: list[str]
    model: str
    status: str                       # ok | partial


@dataclass
class _Validated:
    header: dict[str, Optional[HeaderField]]
    items: list[AIItem]
    rejected: int
    not_found: list[str]


def _error_summary(exc: ValidationError) -> str:
    # loc + msg only: never the input value, which could contain document text
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])


def validate_payload(raw: dict) -> _Validated:
    if "items" not in raw and "not_found" not in raw:
        raise MalformedAIResponse("The AI reply had neither 'items' nor 'not_found'.")
    items_raw = raw.get("items") or []
    if not isinstance(items_raw, list):
        raise MalformedAIResponse("'items' must be a list.")
    items: list[AIItem] = []
    rejected, first_problem = 0, ""
    for entry in items_raw[:MAX_ITEMS_PER_BATCH]:
        try:
            items.append(AIItem.model_validate(entry))
        except ValidationError as exc:
            rejected += 1
            first_problem = first_problem or _error_summary(exc)
    if items_raw and not items:
        raise MalformedAIResponse(f"No item matched the required shape ({first_problem}).")
    header: dict[str, Optional[HeaderField]] = {}
    for key in HEADER_FIELDS:
        value = raw.get(key)
        header[key] = None
        if value not in (None, ""):
            try:
                header[key] = HeaderField.model_validate(value)
            except ValidationError:
                rejected += 1
    not_found = [str(x).strip()[:120] for x in (raw.get("not_found") or []) if isinstance(x, str) and x.strip()][:30]
    return _Validated(header, items, rejected, not_found)


def _ask(provider: AIProvider, user_prompt: str) -> _Validated:
    """One call plus ONE repair attempt if the reply is not usable. Provider errors propagate."""
    prompt, problem = user_prompt, ""
    for _ in range(2):
        text = provider.generate_json(SYSTEM_PROMPT, prompt)
        try:
            return validate_payload(parse_json_text(text))
        except MalformedAIResponse as exc:
            problem = str(exc)
            prompt = user_prompt + "\n\n" + build_repair_prompt(problem)
    raise ExtractionFailed("ai_malformed", f"The AI reply could not be understood, even after a retry ({problem})")


def _span(first: int, count: int) -> str:
    return f"{first}" if count == 1 else f"{first}-{first + count - 1}"


def _analyse(provider: AIProvider, first: int, texts: Sequence[str], warnings: list[str],
             depth: int = 0) -> tuple[list[_Validated], Optional[Exception], bool]:
    """Analyse one run of pages. Returns (results, error, was_split); error is None when everything worked.

    If the AI times out or runs out of room on a run of several pages, the run is split in half and each
    half is tried again (was_split is then True, so the caller can use smaller batches from now on).
    Fatal provider errors (bad key, unknown model, quota) still propagate immediately.
    """
    try:
        return [_ask(provider, build_user_prompt(first, texts))], None, False
    except AIProviderError as exc:
        if exc.code in FATAL_CODES:
            raise
        error: Exception = exc
    except ExtractionFailed as exc:
        error = exc
    too_big = isinstance(error, AIProviderError) and error.code in SPLITTABLE_CODES
    if too_big and len(texts) > 1 and depth < MAX_SPLIT_DEPTH:
        middle = len(texts) // 2
        results: list[_Validated] = []
        last_error: Optional[Exception] = None
        for start, part in ((first, texts[:middle]), (first + middle, texts[middle:])):
            got, err, _ = _analyse(provider, start, part, warnings, depth + 1)
            results.extend(got)
            last_error = err or last_error
        return results, last_error, True
    warnings.append(f"Pages {_span(first, len(texts))} could not be analysed: {getattr(error, 'message', error)}")
    return [], error, False


def _date_from_quote(quote: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    found = find_dates(quote)
    if not found:
        return None, None, "No date was found in the quote."
    if len(found) > 1:
        return None, "needs_review", "The quote contains several dates; choose the right one."
    d = found[0]
    return d.iso, d.status, d.reason


def run_pipeline(provider: AIProvider, pages: Sequence[str], batch_chars: int) -> PipelineResult:
    if not any(p.strip() for p in pages):
        raise ExtractionFailed("no_text", "There is no readable text to analyse.")
    index = PageIndex(pages)
    validated: list[_Validated] = []
    warnings: list[str] = []
    last_error: Optional[Exception] = None

    chars, position, slow_in_a_row = batch_chars, 0, 0
    while position < len(pages):
        # Next batch of whole pages, at the CURRENT size (it shrinks if the AI struggles with big ones).
        texts = batch_pages(pages[position:], chars)[0][1]
        first, position = position + 1, position + len(texts)
        results, error, was_split = _analyse(provider, first, texts, warnings)
        validated.extend(results)
        if was_split:
            # Batches this big are too slow: use smaller ones from now on (never below the floor, never bigger).
            chars = max(min(chars, MIN_BATCH_CHARS), chars // 2)
        if error is None:
            slow_in_a_row = 0
            continue
        last_error = error
        if isinstance(error, AIProviderError) and error.code in STOP_AFTER_PROVIDER_FAILURE:
            if not validated:
                raise error
            if position < len(pages):
                warnings.append(f"Stopped after the AI provider remained unavailable. Pages {position + 1} onward "
                                "were not analysed.")
            break
        too_big = isinstance(error, AIProviderError) and error.code in SPLITTABLE_CODES
        if too_big and not validated:
            raise error   # nothing has worked at all: report it now instead of waiting through every batch
        slow_in_a_row = slow_in_a_row + 1 if too_big else 0
        if slow_in_a_row >= MAX_CONSECUTIVE_SLOW and position < len(pages):
            warnings.append(f"Stopped early after repeated AI timeouts. Pages {position + 1} onward "
                            "were not analysed.")
            break

    if not validated:
        if last_error:
            raise last_error
        raise ExtractionFailed("ai_empty", "The AI returned nothing usable.")

    items: list[ReviewItem] = []
    seen: set[tuple[str, str, str]] = set()
    rejected = sum(v.rejected for v in validated)
    for v in validated:
        for ai in v.items:
            check = verify_quote(ai.supporting_quote, ai.source_page, index)
            key = (ai.category, ai.name.casefold(), normalise(ai.supporting_quote))
            if key in seen:
                continue
            seen.add(key)
            item = ReviewItem(
                category=ai.category, name=ai.name, explanation=ai.explanation,
                supporting_quote=ai.supporting_quote, source_page=check.page or ai.source_page,
                quote_check=check.status, quote_note=check.reason, requirement_level=ai.requirement_level,
                condition=ai.condition, event_key=ai.event_key, outcome=ai.outcome, depends_on=ai.depends_on,
                missing_information=ai.missing_information)
            if ai.category == "deadline":
                if check.status == VERIFIED:
                    item.date_iso, item.date_status, item.date_reason = _date_from_quote(ai.supporting_quote)
                else:
                    item.date_reason = "No date was taken because the quote could not be verified."
            items.append(item)
    items.sort(key=lambda i: i.source_page)

    header: dict[str, Optional[HeaderValue]] = {k: None for k in HEADER_FIELDS}
    for key in HEADER_FIELDS:
        for v in validated:
            h = v.header.get(key)
            if not h:
                continue
            check = verify_quote(h.supporting_quote, h.source_page, index)
            candidate = HeaderValue(h.value, check.page, check.status, check.reason)
            current = header[key]
            if current is None or (current.quote_check != VERIFIED and check.status == VERIFIED):
                header[key] = candidate
            elif current.value.casefold() != h.value.casefold():
                warnings.append(f"The {key.replace('_', ' ')} was read differently in different parts of the "
                                f"document ('{current.value}' and '{h.value}'). Please check it.")

    if rejected:
        warnings.append(f"{rejected} AI suggestion(s) had an invalid shape and were discarded.")
    if not items:
        warnings.append("No requirements were extracted from this document.")
    not_found = sorted({t for v in validated for t in v.not_found})
    model = getattr(provider, "model", "unknown")
    return PipelineResult(header, items, not_found, warnings, model, "partial" if last_error else "ok")
