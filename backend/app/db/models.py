"""Database tables. Plain SQLAlchemy 2.0 so the same models work on SQLite now and PostgreSQL later.

Privacy note: only the TEXT of admission notices is stored (needed for page references and, later, question
answering). The uploaded PDF file itself and personal identity documents are NOT stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(Base):
    """A draft set of documents plus reviewed extraction. Becomes a journey in Phase 3 (after confirmation)."""
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    # Hash of a high-entropy workspace credential; the credential itself is never stored.
    owner_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    institution: Mapped[Optional[str]] = mapped_column(String(300))
    programme: Mapped[Optional[str]] = mapped_column(String(300))
    academic_year: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="SourceDocument.created_at")
    items: Mapped[list["ExtractedItem"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="ExtractedItem.source_page")
    resolutions: Mapped[list["ConflictResolution"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("analysis_id", "sha256", name="uq_document_per_analysis"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer)
    extraction_status: Mapped[str] = mapped_column(String(20))      # ok | partial | needs_ocr | no_text
    ai_status: Mapped[str] = mapped_column(String(20))              # demo | skipped | ok | partial
    ai_model: Mapped[Optional[str]] = mapped_column(String(100))
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    not_found_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    analysis: Mapped[Analysis] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.number")
    items: Mapped[list["ExtractedItem"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "number", name="uq_page_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    document: Mapped[SourceDocument] = relationship(back_populates="pages")


class ExtractedItem(Base):
    __tablename__ = "extracted_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(Text, default="")                 # AI-generated, never official
    supporting_quote: Mapped[str] = mapped_column(Text)                         # official words (if verified)
    source_page: Mapped[int] = mapped_column(Integer)
    quote_check: Mapped[str] = mapped_column(String(20))                        # verified | needs_review | unverified
    quote_note: Mapped[Optional[str]] = mapped_column(Text)
    requirement_level: Mapped[Optional[str]] = mapped_column(String(20))
    condition: Mapped[Optional[str]] = mapped_column(Text)
    event_key: Mapped[Optional[str]] = mapped_column(String(60))
    outcome: Mapped[Optional[str]] = mapped_column(String(20))
    depends_on_json: Mapped[str] = mapped_column(Text, default="[]")
    missing_information: Mapped[Optional[str]] = mapped_column(Text)
    date_iso: Mapped[Optional[str]] = mapped_column(String(10))
    date_status: Mapped[Optional[str]] = mapped_column(String(20))
    date_reason: Mapped[Optional[str]] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(String(20), default="pending")    # pending|accepted|rejected|edited
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    analysis: Mapped[Analysis] = relationship(back_populates="items")
    document: Mapped[SourceDocument] = relationship(back_populates="items")


class ConflictResolution(Base):
    """A person's explicit decision about a detected conflict. The app never decides this itself."""
    __tablename__ = "conflict_resolutions"
    __table_args__ = (UniqueConstraint("analysis_id", "conflict_key", name="uq_resolution"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    conflict_key: Mapped[str] = mapped_column(String(200))
    chosen_item_id: Mapped[Optional[str]] = mapped_column(String(32))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    analysis: Mapped[Analysis] = relationship(back_populates="resolutions")
