"""Deterministic date finder for Indian admission notices.

Why this exists: the old prototype shared ONE global regex (flag ``g``) between
many ``.test()`` calls. A global regex remembers where its last match ended, so
some sentences were silently skipped. Here every call builds fresh match
objects with ``finditer`` and keeps no state, so the same text always gives the
same result.

Rules:
* A year is NEVER invented. "9 June" with no year is returned as needs_review.
* Numeric dates are read day-first (DD/MM/YYYY, the Indian convention). When
  both numbers could be a month (e.g. 07/06/2027) the date is flagged for
  review, because it could also be read month-first.
* Two-digit years are flagged for review.
* Impossible dates (31 February) are reported as "invalid", never dropped.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Optional, Sequence

OK = "ok"
NEEDS_REVIEW = "needs_review"
INVALID = "invalid"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = (
    r"(?P<mon>January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
)
_FULL_MONTH_NAMES = {n.lower() for n in calendar.month_name if n}
_ORD = r"(?:st|nd|rd|th)?"
_FLAGS = re.IGNORECASE

# Priority order matters: full dates win over partial ones that overlap them.
_DMY_NAME = re.compile(
    rf"\b(?P<d>\d{{1,2}}){_ORD}(?:\s+of)?[\s,-]*{_MONTH}(?![A-Za-z])[\s,.-]*(?P<y>\d{{4}})\b", _FLAGS)
_MDY_NAME = re.compile(
    rf"\b{_MONTH}(?![A-Za-z])[\s.]*(?P<d>\d{{1,2}}){_ORD}(?!\d)[\s,]*(?P<y>\d{{4}})\b", _FLAGS)
_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_NUMERIC = re.compile(
    r"(?<![\d./-])(?P<a>\d{1,2})(?P<sep>[/.-])(?P<b>\d{1,2})(?P=sep)(?P<y>\d{4}|\d{2})(?!\d)")
_DM_NOYEAR = re.compile(
    rf"\b(?P<d>\d{{1,2}}){_ORD}(?:\s+of)?\s+{_MONTH}(?![A-Za-z])(?![\s,.-]*\d{{4}})", _FLAGS)
_MD_NOYEAR = re.compile(
    rf"\b{_MONTH}(?![A-Za-z])\s+(?P<d>\d{{1,2}}){_ORD}(?!\d)(?![\s,]*\d{{4}})", _FLAGS)


@dataclass(frozen=True)
class ParsedDate:
    raw: str                      # exact text found in the document
    start: int                    # character offsets inside the searched text
    end: int
    status: str                   # ok | needs_review | invalid
    date: Optional[date] = None   # None when no safe date can be given
    reason: Optional[str] = None  # why review is needed
    page: Optional[int] = None    # 1-based page, when searched page by page

    @property
    def iso(self) -> Optional[str]:
        return self.date.isoformat() if self.date else None


def _month_number(token: str) -> Optional[int]:
    # "may" as an ordinary English word is not a month: require "May" / "MAY".
    if token.lower().rstrip(".") == "may" and token.rstrip(".") not in ("May", "MAY"):
        return None
    return _MONTHS[token.lower()[:3]]


def _make(raw: str, start: int, end: int, y: int, m: int, d: int,
          note: Optional[str] = None) -> ParsedDate:
    try:
        value = date(y, m, d)
    except ValueError:
        return ParsedDate(raw, start, end, INVALID, None,
                          f"'{raw}' is not a real calendar date.")
    return ParsedDate(raw, start, end, NEEDS_REVIEW if note else OK, value, note)


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(span[0] < t[1] and t[0] < span[1] for t in taken)


def find_dates(text: str) -> list[ParsedDate]:
    """Return every date-like mention in ``text`` in reading order."""
    found: list[ParsedDate] = []
    taken: list[tuple[int, int]] = []

    def add(item: ParsedDate) -> None:
        found.append(item)
        taken.append((item.start, item.end))

    for m in _DMY_NAME.finditer(text):
        mon = _month_number(m.group("mon"))
        if mon is None or _overlaps(m.span(), taken):
            continue
        add(_make(m.group(0), *m.span(), int(m.group("y")), mon, int(m.group("d"))))

    for m in _MDY_NAME.finditer(text):
        mon = _month_number(m.group("mon"))
        if mon is None or _overlaps(m.span(), taken):
            continue
        add(_make(m.group(0), *m.span(), int(m.group("y")), mon, int(m.group("d"))))

    for m in _ISO.finditer(text):
        if _overlaps(m.span(), taken):
            continue
        add(_make(m.group(0), *m.span(), int(m.group("y")), int(m.group("m")), int(m.group("d"))))

    for m in _NUMERIC.finditer(text):
        if _overlaps(m.span(), taken):
            continue
        a, b, ytxt = int(m.group("a")), int(m.group("b")), m.group("y")
        year = int(ytxt) if len(ytxt) == 4 else 2000 + int(ytxt)
        notes: list[str] = []
        if len(ytxt) == 2:
            notes.append(f"Two-digit year '{ytxt}' was read as {year}.")
        if b <= 12 and a <= 31:                       # day-first
            day, month = a, b
            if a <= 12 and a != b:
                notes.append(
                    f"Could be {a} {calendar.month_name[b]} or {b} {calendar.month_name[a]}; "
                    "read as day-first (DD/MM), the Indian convention. Please confirm.")
        elif a <= 12 and b <= 31:                     # only month-first is possible
            day, month = b, a
            notes.append("Only month-first (MM/DD) makes sense for these numbers. Please confirm.")
        else:
            continue                                  # not a date (e.g. 60.5.25)
        add(_make(m.group(0), *m.span(), year, month, day, " ".join(notes) or None))

    for pattern in (_DM_NOYEAR, _MD_NOYEAR):
        for m in pattern.finditer(text):
            mon = _month_number(m.group("mon"))
            if mon is None or _overlaps(m.span(), taken):
                continue
            raw, (start, end) = m.group(0), m.span()
            token = m.group("mon")
            # A trailing "." is part of the date only for abbreviations (e.g. "Sept.").
            if raw.endswith(".") and token.lower() in _FULL_MONTH_NAMES:
                raw, end = raw[:-1], end - 1
            add(ParsedDate(raw, start, end, NEEDS_REVIEW, None,
                           "The document gives no year for this date. A year was not assumed."))

    return sorted(found, key=lambda p: p.start)


def has_date(text: str) -> bool:
    return bool(find_dates(text))


def find_dates_in_pages(pages: Sequence[str]) -> list[ParsedDate]:
    """Search page by page so every date keeps its 1-based page number."""
    result: list[ParsedDate] = []
    for number, text in enumerate(pages, start=1):
        result.extend(replace(item, page=number) for item in find_dates(text))
    return result
