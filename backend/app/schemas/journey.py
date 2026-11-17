"""API shapes for the journey preview. They mirror the engine's dataclasses 1:1."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = ("Preview only: nothing is saved. Steps marked 'suggested' and the 'general guidance' text are LIFEPATH's "
              "own general advice, not text from your documents. Always confirm details in the official notice.")


class SourceRefOut(BaseModel):
    item_id: str
    document_name: str
    page: int
    quote: str                       # official words from the notice
    explanation: str                 # AI-written reading, NOT official
    evidence: str                    # verified | reviewer_accepted
    condition: Optional[str] = None


class DocRefOut(BaseModel):
    name: str
    level: str
    condition: Optional[str] = None
    format_or_missing_note: Optional[str] = None
    source: SourceRefOut


class StepDeadlineOut(BaseModel):
    label: str
    event_key: Optional[str] = None
    date_iso: Optional[str] = None
    date_status: Optional[str] = None
    reason: Optional[str] = None
    source: SourceRefOut


class DependencyOut(BaseModel):
    step_key: str
    basis: str                       # notice | general_flow


class GuidanceOut(BaseModel):
    why_it_matters: str
    what_to_do: str
    origin: str


class StepOut(BaseModel):
    key: str
    order: int
    title: str
    kind: str                        # supported | suggested
    status: str                      # completed | available | locked | conditional | not_applicable | needs_review
    locked_reason: Optional[str] = None
    branch: Optional[str] = None
    depends_on: list[DependencyOut]
    sources: list[SourceRefOut]
    deadlines: list[StepDeadlineOut]
    documents: list[DocRefOut]
    guidance: Optional[GuidanceOut] = None
    notes: list[str]
    needs_review: bool


class SkippedItemOut(BaseModel):
    item_id: str
    name: str
    reason: str


class NoteOut(BaseModel):
    name: str
    explanation: str
    source: SourceRefOut


class ProgressOut(BaseModel):
    completed: int
    total: int
    percent: int
    note: str


class JourneyOut(BaseModel):
    preview: bool = True
    disclaimer: str = DISCLAIMER
    meta: dict[str, Optional[str]]
    outcome: Optional[str] = None
    steps: list[StepOut]
    progress: ProgressOut
    gaps: list[str]
    warnings: list[str]
    skipped_items: list[SkippedItemOut]
    unattached_deadlines: list[StepDeadlineOut]
    fees: list[NoteOut]
    notice_warnings: list[NoteOut]


class JourneyPreviewIn(BaseModel):
    """Optional input. Without a body, no outcome is recorded and no step is marked done."""
    model_config = ConfigDict(extra="forbid")
    outcome: Optional[Literal["selected", "waitlisted", "not_selected"]] = None
    completed: list[str] = Field(default_factory=list, max_length=100)
