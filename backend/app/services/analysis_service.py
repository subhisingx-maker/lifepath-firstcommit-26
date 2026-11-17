"""Saving, reading and editing draft analyses. No HTTP code in here."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Analysis, ConflictResolution, DocumentPage, ExtractedItem, SourceDocument
from app.schemas.analyses import (AnalysisOut, ConflictOut, ConflictSideOut, Counts, DocumentOut, ItemOut,
                                  NotFoundOut)
from app.schemas.documents import AIInfo, DateOut
from app.services.ai_service import AIStatus
from app.services.conflict_detector import Conflict, ConflictItem, detect_conflicts
from app.services.deadline_parser import find_dates_in_pages
from app.services.extraction_pipeline import PipelineResult
from app.services.pdf_extractor import ExtractionResult

STATUS_LABELS = {
    "verified": "Verified against source", "unverified": "Unverified", "needs_review": "Needs review",
    "not_found": "Not found", "conflict": "Conflict detected",
}


class DuplicateDocument(Exception):
    pass


class NotFound(Exception):
    pass


class InvalidEdit(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_analysis(db: Session, analysis_id: str) -> Analysis:
    found = db.get(Analysis, analysis_id)
    if found is None:
        raise NotFound("analysis")
    return found


def new_analysis(title: Optional[str] = None) -> Analysis:
    return Analysis(title=(title or None))


def add_document(db: Session, analysis: Analysis, extraction: ExtractionResult, digest: str,
                 pipeline: Optional[PipelineResult], ai_enabled: bool) -> SourceDocument:
    if any(d.sha256 == digest for d in analysis.documents):
        raise DuplicateDocument()
    if not ai_enabled:
        ai_status = "demo"
    elif pipeline is None:
        ai_status = "skipped"                       # AI is on, but the file has no readable text
    else:
        ai_status = pipeline.status

    warnings = list(extraction.analysis.warnings)
    if pipeline:
        warnings += pipeline.warnings
    elif ai_enabled:
        warnings.append("AI analysis was skipped because the document has no readable text.")

    doc = SourceDocument(
        filename=extraction.filename, sha256=digest, page_count=extraction.page_count,
        extraction_status=extraction.analysis.status, ai_status=ai_status,
        ai_model=pipeline.model if pipeline else None, warnings_json=json.dumps(warnings),
        not_found_json=json.dumps(pipeline.not_found if pipeline else []))
    doc.pages = [DocumentPage(number=p.number, text=p.text) for p in extraction.pages]
    analysis.documents.append(doc)

    if pipeline:
        for key in ("institution", "programme", "academic_year"):
            h = pipeline.header.get(key)
            if h and h.quote_check == "verified" and not getattr(analysis, key):
                setattr(analysis, key, h.value)
        for it in pipeline.items:
            analysis.items.append(ExtractedItem(
                document=doc, category=it.category, name=it.name, explanation=it.explanation,
                supporting_quote=it.supporting_quote, source_page=it.source_page, quote_check=it.quote_check,
                quote_note=it.quote_note, requirement_level=it.requirement_level, condition=it.condition,
                event_key=it.event_key, outcome=it.outcome, depends_on_json=json.dumps(it.depends_on),
                missing_information=it.missing_information, date_iso=it.date_iso, date_status=it.date_status,
                date_reason=it.date_reason))
    db.add(analysis)
    db.commit()
    return doc


def _conflicts(analysis: Analysis) -> list[Conflict]:
    names = {d.id: d.filename for d in analysis.documents}
    items = [ConflictItem(
        id=i.id, document_id=i.document_id, document_name=names.get(i.document_id, "?"), category=i.category,
        name=i.name, page=i.source_page, quote=i.supporting_quote, level=i.requirement_level,
        event_key=i.event_key, date_iso=i.date_iso) for i in analysis.items if i.review_state != "rejected"]
    return detect_conflicts(items)


def conflicts_with_resolutions(analysis: Analysis) -> tuple[list[Conflict], dict[str, ConflictResolution]]:
    """Current conflicts plus the human decisions recorded so far (used by the journey preview)."""
    return _conflicts(analysis), {r.conflict_key: r for r in analysis.resolutions}


def build_detail(analysis: Analysis, ai: AIStatus) -> AnalysisOut:
    resolutions = {r.conflict_key: r for r in analysis.resolutions}
    conflicts = _conflicts(analysis)
    in_open_conflict: dict[str, list[str]] = {}
    conflict_keys: dict[str, list[str]] = {}
    conflict_out: list[ConflictOut] = []
    for c in conflicts:
        res = resolutions.get(c.key)
        for s in c.sides:
            conflict_keys.setdefault(s.item_id, []).append(c.key)
            if res is None:
                in_open_conflict.setdefault(s.item_id, []).append(c.key)
        conflict_out.append(ConflictOut(
            key=c.key, kind=c.kind, title=c.title, resolved=res is not None,
            chosen_item_id=res.chosen_item_id if res else None, note=res.note if res else None,
            sides=[ConflictSideOut(item_id=s.item_id, document_name=s.document_name, page=s.page,
                                   quote=s.quote, value=s.value) for s in c.sides]))

    names = {d.id: d.filename for d in analysis.documents}
    items_out: list[ItemOut] = []
    for i in analysis.items:
        status = "conflict" if i.id in in_open_conflict else i.quote_check
        items_out.append(ItemOut(
            id=i.id, document_id=i.document_id, document_name=names.get(i.document_id, "?"),
            category=i.category, name=i.name, explanation=i.explanation, supporting_quote=i.supporting_quote,
            source_page=i.source_page, status=status, status_label=STATUS_LABELS.get(status, status),
            quote_check=i.quote_check, quote_note=i.quote_note, requirement_level=i.requirement_level,
            condition=i.condition, event_key=i.event_key, outcome=i.outcome,
            depends_on=json.loads(i.depends_on_json or "[]"), missing_information=i.missing_information,
            date_iso=i.date_iso, date_status=i.date_status, date_reason=i.date_reason,
            review_state=i.review_state, user_edited=i.user_edited,
            conflict_keys=conflict_keys.get(i.id, [])))

    docs_out: list[DocumentOut] = []
    not_found: list[NotFoundOut] = []
    for d in analysis.documents:
        dates: list[DateOut] = []
        if d.ai_status in ("demo", "skipped"):     # no AI items exist, so show deterministic dates
            found = find_dates_in_pages([p.text for p in d.pages])
            dates = [DateOut(raw=x.raw, page=x.page, status=x.status, iso=x.iso, reason=x.reason) for x in found]
        docs_out.append(DocumentOut(
            id=d.id, filename=d.filename, page_count=d.page_count, extraction_status=d.extraction_status,
            ai_status=d.ai_status, ai_model=d.ai_model, warnings=json.loads(d.warnings_json or "[]"),
            dates=dates))
        not_found += [NotFoundOut(document_name=d.filename, topic=t) for t in json.loads(d.not_found_json or "[]")]

    return AnalysisOut(
        id=analysis.id, title=analysis.title, institution=analysis.institution, programme=analysis.programme,
        academic_year=analysis.academic_year, status=analysis.status, created_at=analysis.created_at,
        documents=docs_out, items=items_out, conflicts=conflict_out, not_found=not_found,
        counts=Counts(items=len(items_out),
                      pending_review=sum(1 for i in analysis.items if i.review_state == "pending"),
                      unresolved_conflicts=sum(1 for c in conflict_out if not c.resolved)),
        ai=AIInfo(mode=ai.mode, message=ai.message))


def edit_item(db: Session, analysis: Analysis, item_id: str, changes: dict) -> ExtractedItem:
    item = next((i for i in analysis.items if i.id == item_id), None)
    if item is None:
        raise NotFound("item")
    content_changed = False
    if "name" in changes:
        if not changes["name"]:
            raise InvalidEdit("name cannot be empty.")
        item.name = changes["name"]
        content_changed = True
    if "explanation" in changes:
        item.explanation = changes["explanation"] or ""
        content_changed = True
    if "condition" in changes:
        item.condition = changes["condition"] or None
        content_changed = True
    if "requirement_level" in changes:
        if item.category != "document":
            raise InvalidEdit("requirement_level can only be set on document items.")
        item.requirement_level = changes["requirement_level"]
        content_changed = True
    if "date_iso" in changes:
        if item.category != "deadline":
            raise InvalidEdit("date_iso can only be set on deadline items.")
        value = changes["date_iso"]
        if value is None:
            item.date_iso, item.date_status, item.date_reason = None, None, "Date cleared by you."
        else:
            try:
                date.fromisoformat(value)
            except ValueError:
                raise InvalidEdit("date_iso must be a real date in YYYY-MM-DD format.") from None
            item.date_iso, item.date_status, item.date_reason = value, "user_confirmed", "Entered by you."
        content_changed = True
    if content_changed:
        item.user_edited = True
        item.review_state = "edited"
    if "review_state" in changes and changes["review_state"] is not None:
        item.review_state = changes["review_state"]
    db.commit()
    return item


def resolve_conflict(db: Session, analysis: Analysis, key: str, chosen_item_id: Optional[str],
                     note: Optional[str]) -> None:
    conflict = next((c for c in _conflicts(analysis) if c.key == key), None)
    if conflict is None:
        raise NotFound("conflict")
    if chosen_item_id is not None and chosen_item_id not in {s.item_id for s in conflict.sides}:
        raise InvalidEdit("chosen_item_id must be one of the items in this conflict.")
    if chosen_item_id is None and not (note or "").strip():
        raise InvalidEdit("Choose one side, or add a note explaining how you resolved this.")
    existing = next((r for r in analysis.resolutions if r.conflict_key == key), None)
    if existing:
        existing.chosen_item_id, existing.note = chosen_item_id, note
    else:
        analysis.resolutions.append(ConflictResolution(conflict_key=key, chosen_item_id=chosen_item_id, note=note))
    db.commit()
