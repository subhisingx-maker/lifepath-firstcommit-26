from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import __version__
from app.core.config import Settings, get_settings
from app.schemas.documents import (AIInfo, DateOut, ExtractionResponse, HealthResponse, PageOut)
from app.services.ai_service import get_ai_status
from app.services.deadline_parser import find_dates_in_pages
from app.services.pdf_extractor import (ExtractionError, extract_pdf, safe_filename,
                                        validate_upload)

router = APIRouter(prefix="/api")
DEMO_FILE = Path(__file__).resolve().parents[1] / "data" / "demo_journey.json"

_STATUS_FOR_ERROR = {
    "empty_file": 400, "unsupported_type": 415, "too_large": 413,
    "not_a_pdf": 415, "corrupt": 422, "encrypted": 422, "too_many_pages": 413,
}


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    ai = get_ai_status(settings)
    return HealthResponse(
        status="ok", ai_mode=ai.mode, ai_provider=ai.provider, ai_configured=ai.configured,
        ai_message=ai.message, ocr="not_implemented", version=__version__)


@lru_cache
def _demo_journey() -> dict:
    return json.loads(DEMO_FILE.read_text(encoding="utf-8"))


@router.get("/demo/journey")
def demo_journey() -> dict:
    """Bundled FICTIONAL journey. Needs no account, no upload, no API key."""
    return _demo_journey()


@router.post("/documents/extract", response_model=ExtractionResponse)
async def extract_document(file: UploadFile = File(...),
                           settings: Settings = Depends(get_settings)) -> ExtractionResponse:
    limit = settings.max_upload_bytes
    data = await file.read(limit + 1)          # never read more than limit + 1 byte
    name = safe_filename(file.filename)
    try:
        validate_upload(name, data, limit)
        result = await run_in_threadpool(extract_pdf, data, name, settings.max_pdf_pages)
    except ExtractionError as err:
        raise HTTPException(status_code=_STATUS_FOR_ERROR.get(err.code, 422),
                            detail={"code": err.code, "message": err.message})

    ai = get_ai_status(settings)
    dates = find_dates_in_pages([p.text for p in result.pages])
    return ExtractionResponse(
        filename=result.filename, page_count=result.page_count, status=result.analysis.status,
        warnings=result.analysis.warnings, failed_pages=result.analysis.failed_pages,
        scanned_pages=result.analysis.scanned_pages, blank_pages=result.analysis.blank_pages,
        pages=[PageOut(number=p.number, text=p.text, char_count=p.char_count,
                       image_count=p.image_count, error=p.error) for p in result.pages],
        dates=[DateOut(raw=d.raw, page=d.page, status=d.status, iso=d.iso, reason=d.reason)
               for d in dates],
        ai=AIInfo(mode=ai.mode, message=ai.message))
