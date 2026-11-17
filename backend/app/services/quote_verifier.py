"""Check an AI-supplied quote against the real document text.

"verified" here means ONE thing: the quoted words really appear in the source
document (on the stated page, or on a page we then correct it to). It does NOT
mean the AI's explanation of the quote is right. The explanation always stays
labelled as AI-generated.

Statuses: verified | needs_review | unverified
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, Sequence

VERIFIED = "verified"
NEEDS_REVIEW = "needs_review"
UNVERIFIED = "unverified"

MIN_QUOTE_CHARS = 12
MIN_QUOTE_WORDS = 3
FUZZY_THRESHOLD = 0.88

_MAP = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
                      "\u2014": "-", "\u2212": "-", "\u00a0": " ", "\u200b": ""})


def normalise(text: str) -> str:
    """Make PDF text and quotes comparable: ligatures, curly quotes, dashes, spacing, case."""
    t = unicodedata.normalize("NFKC", text or "").translate(_MAP)
    return re.sub(r"\s+", " ", t).strip().casefold()


class PageIndex:
    """Pages normalised once so many quotes can be checked cheaply."""

    def __init__(self, pages: Sequence[str]) -> None:
        self.norm = [normalise(p) for p in pages]

    def __len__(self) -> int:
        return len(self.norm)

    def pages_containing(self, needle: str) -> list[int]:
        return [i + 1 for i, text in enumerate(self.norm) if needle in text]


@dataclass(frozen=True)
class QuoteCheck:
    status: str
    page: Optional[int]       # page where the text was actually found (1-based)
    reason: Optional[str]
    score: float = 0.0


def _best_similarity(q: str, page: str) -> float:
    segments = [s for s in re.split(r"(?<=[.;:!?])\s+", page) if s]
    best = 0.0
    for i in range(len(segments)):
        for width in (1, 2):
            window = " ".join(segments[i:i + width])
            if not (0.5 * len(q) <= len(window) <= 2 * len(q)):
                continue
            m = difflib.SequenceMatcher(None, q, window, autojunk=False)
            if m.real_quick_ratio() < FUZZY_THRESHOLD or m.quick_ratio() < FUZZY_THRESHOLD:
                continue
            best = max(best, m.ratio())
    return best


def verify_quote(quote: str, claimed_page: int, index: PageIndex) -> QuoteCheck:
    q = normalise(quote)
    if len(q) < MIN_QUOTE_CHARS or len(q.split()) < MIN_QUOTE_WORDS:
        return QuoteCheck(NEEDS_REVIEW, None, "The quote is too short to verify reliably.")

    page_ok = 1 <= claimed_page <= len(index)

    if "..." in q:  # an elided quote is not an exact passage
        parts = [p.strip() for p in q.split("...") if len(p.strip()) >= MIN_QUOTE_CHARS]
        if page_ok and parts:
            text, pos = index.norm[claimed_page - 1], 0
            for part in parts:
                found = text.find(part, pos)
                if found == -1:
                    break
                pos = found + len(part)
            else:
                return QuoteCheck(NEEDS_REVIEW, claimed_page,
                                  "The quote skips words (\u2026), so it is not an exact passage.")
        return QuoteCheck(UNVERIFIED, None, "The quote could not be found in the document text.")

    if page_ok and q in index.norm[claimed_page - 1]:
        return QuoteCheck(VERIFIED, claimed_page, None, 1.0)

    others = [p for p in index.pages_containing(q) if p != claimed_page]
    if len(others) == 1:
        note = (f"Page corrected from {claimed_page} to {others[0]}."
                if page_ok else f"Page set to {others[0]}; the stated page was invalid.")
        return QuoteCheck(VERIFIED, others[0], note, 1.0)
    if len(others) > 1:
        return QuoteCheck(NEEDS_REVIEW, others[0],
                          f"The quote appears on several pages ({', '.join(map(str, others))}).", 1.0)

    candidates = [claimed_page] if page_ok else []
    candidates += [p for p in range(1, len(index) + 1) if p != claimed_page]
    best_score, best_page = 0.0, None
    for number in candidates:
        score = _best_similarity(q, index.norm[number - 1])
        if score > best_score:
            best_score, best_page = score, number
    if best_page is not None and best_score >= FUZZY_THRESHOLD:
        return QuoteCheck(NEEDS_REVIEW, best_page,
                          f"The closest passage on page {best_page} differs from the quote "
                          f"({round(best_score * 100)}% similar).", best_score)
    return QuoteCheck(UNVERIFIED, None, "The quote could not be found in the document text.", best_score)
