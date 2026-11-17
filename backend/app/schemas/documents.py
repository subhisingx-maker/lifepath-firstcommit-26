"""API response shapes (validated by Pydantic)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    ai_mode: str
    ai_provider: str
    ai_configured: bool
    ai_message: str
    ocr: str
    version: str


class PageOut(BaseModel):
    number: int
    text: str
    char_count: int
    image_count: int
    error: Optional[str] = None


class DateOut(BaseModel):
    raw: str
    page: Optional[int]
    status: str                  # ok | needs_review | invalid
    iso: Optional[str] = None    # null when no safe date can be given
    reason: Optional[str] = None


class AIInfo(BaseModel):
    mode: str
    message: str


class ExtractionResponse(BaseModel):
    filename: str
    page_count: int
    status: str                  # ok | partial | needs_ocr | no_text
    warnings: list[str]
    failed_pages: list[int]
    scanned_pages: list[int]
    blank_pages: list[int]
    pages: list[PageOut]
    dates: list[DateOut]
    ai: AIInfo


class ErrorBody(BaseModel):
    code: str
    message: str
