"""Safe, page-by-page PDF text extraction with PyMuPDF.

Design rules:
* Page numbers are preserved (1-based) and every page is reported.
* Nothing is silently skipped: a page that fails is returned with its error.
* Scanned (image-only) pages are detected and reported. OCR is NOT implemented
  yet, so their content is not read and the result says so.
* Document text is untrusted data. It is never executed or logged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

MIN_TEXT_CHARS = 25  # fewer characters than this = "no real text on this page"
OCR_NOTE = "OCR is not implemented yet, so the content of these pages was not read."


class ExtractionError(Exception):
    """A problem with the uploaded file. ``code`` is stable, ``message`` is user-facing."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    image_count: int = 0
    error: str | None = None

    @property
    def char_count(self) -> int:
        return len(self.text.strip())

    @property
    def has_text(self) -> bool:
        return self.error is None and self.char_count >= MIN_TEXT_CHARS

    @property
    def likely_scanned(self) -> bool:
        return self.error is None and self.char_count < MIN_TEXT_CHARS and self.image_count > 0

    @property
    def is_blank(self) -> bool:
        return self.error is None and self.char_count < MIN_TEXT_CHARS and self.image_count == 0


@dataclass(frozen=True)
class PageAnalysis:
    status: str  # ok | partial | needs_ocr | no_text
    failed_pages: list[int] = field(default_factory=list)
    scanned_pages: list[int] = field(default_factory=list)
    blank_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionResult:
    filename: str
    page_count: int
    pages: list[PageText]
    analysis: PageAnalysis


def _pages_text(numbers: Sequence[int]) -> str:
    return ", ".join(str(n) for n in numbers)


def analyse_pages(pages: Sequence[PageText]) -> PageAnalysis:
    """Decide how trustworthy an extraction is. Pure function, easy to test."""
    failed = [p.number for p in pages if p.error]
    scanned = [p.number for p in pages if p.likely_scanned]
    blank = [p.number for p in pages if p.is_blank]
    readable = [p for p in pages if p.has_text]
    warnings: list[str] = []

    if failed:
        warnings.append(f"Could not read page(s) {_pages_text(failed)}. See each page's error.")
    if scanned:
        warnings.append(f"Page(s) {_pages_text(scanned)} look scanned (images, no text). {OCR_NOTE}")
    if blank:
        warnings.append(f"Page(s) {_pages_text(blank)} appear blank.")

    if not readable:
        status = "needs_ocr" if scanned else "no_text"
        if status == "no_text":
            warnings.append("No readable text was found in this file.")
    elif pages and len(scanned) / len(pages) >= 0.5:
        status = "needs_ocr"
    elif failed or scanned or blank:
        status = "partial"
    else:
        status = "ok"
    return PageAnalysis(status, failed, scanned, blank, warnings)


def safe_filename(name: str | None) -> str:
    """Display-safe name: no folders (Windows or Unix), no control characters."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return (base or "document.pdf")[:120]


def validate_upload(filename: str, data: bytes, max_bytes: int) -> None:
    """Cheap checks before PyMuPDF touches the bytes."""
    if not data:
        raise ExtractionError("empty_file", "The file is empty.")
    if not filename.lower().endswith(".pdf"):
        raise ExtractionError(
            "unsupported_type",
            "Only PDF files are supported. Image files need OCR, which is not implemented yet.")
    if len(data) > max_bytes:
        raise ExtractionError(
            "too_large", f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    if b"%PDF-" not in data[:1024]:
        raise ExtractionError("not_a_pdf", "This file does not look like a real PDF.")


def extract_pdf(data: bytes, filename: str, max_pages: int) -> ExtractionResult:
    import pymupdf  # imported here so the rest of the app works without it

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types for bad files
        raise ExtractionError(
            "corrupt", "This PDF is damaged and could not be opened.") from exc

    try:
        if doc.needs_pass or doc.is_encrypted:
            raise ExtractionError(
                "encrypted", "This PDF is password-protected. Remove the password and try again.")
        if doc.page_count == 0:
            raise ExtractionError("corrupt", "This PDF has no pages.")
        if doc.page_count > max_pages:
            raise ExtractionError(
                "too_many_pages",
                f"This PDF has {doc.page_count} pages. The limit is {max_pages}.")

        pages: list[PageText] = []
        for index in range(doc.page_count):
            number = index + 1
            try:
                page = doc.load_page(index)
                text = page.get_text("text")
                images = len(page.get_images(full=True))
                pages.append(PageText(number, text, images))
            except Exception as exc:  # report it, never hide it
                pages.append(PageText(number, "", 0, error=f"{type(exc).__name__}: {exc}"))
        return ExtractionResult(filename, len(pages), pages, analyse_pages(pages))
    finally:
        doc.close()
