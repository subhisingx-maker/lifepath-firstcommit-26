"""Find places where documents (or pages) disagree. Never picks a winner.

Two kinds are detected, both deterministically:
* deadline  - same event_key, different calendar dates
* document  - same document, different requirement levels (e.g. mandatory vs not_required)

A conflict lists EVERY side with its document name and page so a person can
decide. Which side is correct (for example a corrigendum) is a human decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

_STOP = {"the", "a", "an", "of", "copy", "copies", "scanned", "original", "for", "and", "valid"}
_LEVELS = {"mandatory", "conditional", "optional", "not_required"}  # not_specified never conflicts


@dataclass(frozen=True)
class ConflictItem:
    id: str
    document_id: str
    document_name: str
    category: str
    name: str
    page: int
    quote: str
    level: Optional[str] = None
    event_key: Optional[str] = None
    date_iso: Optional[str] = None


@dataclass(frozen=True)
class ConflictSide:
    item_id: str
    document_name: str
    page: int
    quote: str
    value: str            # a date (ISO) or a requirement level


@dataclass(frozen=True)
class Conflict:
    key: str              # stable id, e.g. "deadline:registration_close"
    kind: str             # deadline | document
    title: str
    sides: list[ConflictSide] = field(default_factory=list)


def _tokens(name: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", name.casefold())
    return frozenset(w for w in words if w not in _STOP)


def _same_document(a: frozenset[str], b: frozenset[str]) -> bool:
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return len(small) >= 2 and small <= big


def detect_conflicts(items: Sequence[ConflictItem]) -> list[Conflict]:
    conflicts: list[Conflict] = []

    # ---- deadlines
    by_event: dict[str, list[ConflictItem]] = {}
    for it in items:
        if it.category == "deadline" and it.event_key and it.date_iso:
            by_event.setdefault(it.event_key, []).append(it)
    for key, group in sorted(by_event.items()):
        if len({g.date_iso for g in group}) > 1:
            conflicts.append(Conflict(
                f"deadline:{key}", "deadline", f"Different dates for '{key.replace('_', ' ')}'",
                [ConflictSide(g.id, g.document_name, g.page, g.quote, g.date_iso or "") for g in group]))

    # ---- documents
    docs = [it for it in items if it.category == "document" and it.name.strip() and it.level in _LEVELS]
    groups: list[list[ConflictItem]] = []
    for it in docs:
        toks = _tokens(it.name)
        for g in groups:
            if _same_document(toks, _tokens(g[0].name)):
                g.append(it)
                break
        else:
            groups.append([it])
    for g in groups:
        if len({x.level for x in g}) > 1:
            label = min((x.name for x in g), key=len)
            conflicts.append(Conflict(
                "document:" + "_".join(sorted(_tokens(label))), "document",
                f"Different requirements for '{label}'",
                [ConflictSide(x.id, x.document_name, x.page, x.quote, x.level or "") for x in g]))
    return conflicts
