"""API shapes for draft analyses (review-and-edit step)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.documents import AIInfo, DateOut
from app.schemas.extraction import RequirementLevel

ReviewState = Literal["pending", "accepted", "rejected", "edited"]


class ItemOut(BaseModel):
    id: str
    document_id: str
    document_name: str
    category: str
    name: str
    explanation: str                    # AI-generated reading. NOT official text.
    supporting_quote: str               # exact words from the notice
    source_page: int
    status: str                         # verified | needs_review | unverified | not_found | conflict
    status_label: str
    quote_check: str                    # the stored check of the quote, before conflicts are considered
    quote_note: Optional[str]
    requirement_level: Optional[str]
    condition: Optional[str]
    event_key: Optional[str]
    outcome: Optional[str]
    depends_on: list[str]
    missing_information: Optional[str]
    date_iso: Optional[str]
    date_status: Optional[str]
    date_reason: Optional[str]
    review_state: str
    user_edited: bool
    conflict_keys: list[str]


class ConflictSideOut(BaseModel):
    item_id: str
    document_name: str
    page: int
    quote: str
    value: str


class ConflictOut(BaseModel):
    key: str
    kind: str
    title: str
    sides: list[ConflictSideOut]
    resolved: bool
    chosen_item_id: Optional[str] = None
    note: Optional[str] = None


class NotFoundOut(BaseModel):
    document_name: str
    topic: str


class DocumentOut(BaseModel):
    id: str
    filename: str
    page_count: int
    extraction_status: str
    ai_status: str                      # demo | skipped | ok | partial
    ai_model: Optional[str]
    warnings: list[str]
    dates: list[DateOut] = Field(default_factory=list)   # filled when no AI extraction was possible


class Counts(BaseModel):
    items: int
    pending_review: int
    unresolved_conflicts: int


class AnalysisOut(BaseModel):
    id: str
    title: Optional[str]
    institution: Optional[str]
    programme: Optional[str]
    academic_year: Optional[str]
    status: str
    created_at: datetime
    documents: list[DocumentOut]
    items: list[ItemOut]
    conflicts: list[ConflictOut]
    not_found: list[NotFoundOut]
    counts: Counts
    ai: AIInfo


class AnalysisSummary(BaseModel):
    id: str
    title: Optional[str]
    institution: Optional[str]
    programme: Optional[str]
    academic_year: Optional[str]
    document_count: int
    created_at: datetime


class AnalysisPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Optional[str] = Field(default=None, max_length=200)
    institution: Optional[str] = Field(default=None, max_length=300)
    programme: Optional[str] = Field(default=None, max_length=300)
    academic_year: Optional[str] = Field(default=None, max_length=100)


class ItemPatch(BaseModel):
    """Only fields that a person may correct. The quote and page are evidence and cannot be edited."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    explanation: Optional[str] = Field(default=None, max_length=600)
    requirement_level: Optional[RequirementLevel] = None
    condition: Optional[str] = Field(default=None, max_length=400)
    date_iso: Optional[str] = Field(default=None, max_length=10)
    review_state: Optional[ReviewState] = None


class ConflictResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    conflict_key: str = Field(min_length=1, max_length=200)
    chosen_item_id: Optional[str] = Field(default=None, max_length=32)
    note: Optional[str] = Field(default=None, max_length=500)


class PageTextOut(BaseModel):
    number: int
    text: str
