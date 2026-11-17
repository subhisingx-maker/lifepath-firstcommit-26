"""Glue between the database and the pure journey engine. No AI, no HTTP, nothing is saved."""
from __future__ import annotations

import json
from typing import Iterable, Optional

from app.db.models import Analysis
from app.services.analysis_service import conflicts_with_resolutions
from app.services.journey_engine import (Journey, JourneyBlocked, JourneyItem, build_journey,
                                         conflict_exclusions)


def build_preview(analysis: Analysis, outcome: Optional[str], completed: Iterable[str]) -> Journey:
    conflicts, resolutions = conflicts_with_resolutions(analysis)

    # Blocks while any conflict has no human decision; otherwise returns the items to leave out.
    excluded = conflict_exclusions(conflicts, {key: r.chosen_item_id for key, r in resolutions.items()})

    if not analysis.items:
        demo = bool(analysis.documents) and all(d.ai_status in ("demo", "skipped") for d in analysis.documents)
        raise JourneyBlocked(
            "no_reviewed_items",
            ("There are no extracted items to build a journey from. In demo mode no items are extracted: add a "
             "Gemini API key to extract requirements, or open the bundled demo journey at /api/demo/journey.")
            if demo else "There are no extracted items to build a journey from yet.")

    names = {d.id: d.filename for d in analysis.documents}
    items = [JourneyItem(
        id=i.id, document_name=names.get(i.document_id, "?"), category=i.category, name=i.name,
        explanation=i.explanation, quote=i.supporting_quote, page=i.source_page, quote_check=i.quote_check,
        review_state=i.review_state, requirement_level=i.requirement_level, condition=i.condition,
        event_key=i.event_key, outcome=i.outcome, depends_on=tuple(json.loads(i.depends_on_json or "[]")),
        missing_information=i.missing_information, date_iso=i.date_iso, date_status=i.date_status,
        date_reason=i.date_reason) for i in analysis.items]
    not_found = [t for d in analysis.documents for t in json.loads(d.not_found_json or "[]")]
    meta = {"title": analysis.title, "institution": analysis.institution, "programme": analysis.programme,
            "academic_year": analysis.academic_year}
    return build_journey(items, excluded_ids=excluded, outcome=outcome, completed=set(completed), meta=meta,
                         not_found_topics=not_found)
