"""Draft analyses: upload notices, review what was extracted, edit, resolve conflicts, delete."""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.journey import JourneyOut, JourneyPreviewIn
from app.schemas.analyses import (AnalysisOut, AnalysisPatch, AnalysisSummary, ConflictResolveIn, ItemPatch,
                                  PageTextOut)
from app.services import analysis_service as svc
from app.services import journey_service
from app.services.journey_engine import JourneyBlocked
from app.services.ai_service import AIProvider, AIProviderError, get_ai_status, get_provider
from app.services.extraction_pipeline import ExtractionFailed, PipelineResult, run_pipeline
from app.services.pdf_extractor import (ExtractionError, ExtractionResult, extract_pdf, safe_filename,
                                        validate_upload)
from app.services.rate_limiter import SlidingWindowLimiter

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

_EXTRACTION_STATUS = {"empty_file": 400, "unsupported_type": 415, "too_large": 413, "not_a_pdf": 415,
                      "corrupt": 422, "encrypted": 422, "too_many_pages": 413}
_limiter: Optional[SlidingWindowLimiter] = None


def workspace_owner(token: Optional[str] = Header(default=None, alias="X-Workspace-Token")) -> str:
    """Identify one browser workspace without storing its secret on the server."""
    if not token or not re.fullmatch(r"[0-9a-f]{64}", token):
        raise HTTPException(401, {"code": "workspace_required", "message": "Your workspace credential is missing."})
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def reset_limiter() -> None:
    """For tests."""
    global _limiter
    _limiter = None


def rate_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter(settings.ai_rate_limit_per_minute)
    allowed, retry_after = _limiter.check(request.client.host if request.client else "unknown")
    if not allowed:
        raise HTTPException(429, {"code": "too_many_requests",
                                  "message": f"Too many uploads. Try again in {retry_after} seconds."},
                            headers={"Retry-After": str(retry_after)})


def get_ai_provider(settings: Settings = Depends(get_settings)) -> Optional[AIProvider]:
    """None means demo mode (no key). Tests override this with a fake provider."""
    return get_provider(settings) if settings.gemini_api_key else None


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def _ai_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AIProviderError):
        return _err({"rate_limited": 429, "timeout": 504}.get(exc.code, 502), exc.code, exc.message)
    return _err(502, getattr(exc, "code", "ai_failed"), getattr(exc, "message", "The AI step failed."))


async def _process(file: UploadFile, settings: Settings, provider: Optional[AIProvider]
                   ) -> tuple[ExtractionResult, str, Optional[PipelineResult]]:
    """Validate -> extract text -> (if AI is on) extract requirements. Raises before anything is saved."""
    limit = settings.max_upload_bytes
    data = await file.read(limit + 1)
    name = safe_filename(file.filename)
    try:
        validate_upload(name, data, limit)
        extraction = await run_in_threadpool(extract_pdf, data, name, settings.max_pdf_pages)
    except ExtractionError as exc:
        raise _err(_EXTRACTION_STATUS.get(exc.code, 422), exc.code, exc.message)
    pipeline = None
    if provider is not None and extraction.analysis.status not in ("needs_ocr", "no_text"):
        try:
            pipeline = await run_in_threadpool(
                run_pipeline, provider, [p.text for p in extraction.pages], settings.ai_batch_chars)
        except (AIProviderError, ExtractionFailed) as exc:
            raise _ai_http_error(exc)
    return extraction, svc.sha256_hex(data), pipeline


def _detail(analysis, settings: Settings) -> AnalysisOut:
    return svc.build_detail(analysis, get_ai_status(settings))


@router.post("", response_model=AnalysisOut, status_code=201, dependencies=[Depends(rate_limit)])
async def create_analysis(file: UploadFile = File(...), title: Optional[str] = Form(None),
                          settings: Settings = Depends(get_settings), db: Session = Depends(get_db),
                          provider: Optional[AIProvider] = Depends(get_ai_provider),
                          owner: str = Depends(workspace_owner)) -> AnalysisOut:
    """Creates an analysis only if the first document is processed successfully (no empty drafts)."""
    extraction, digest, pipeline = await _process(file, settings, provider)
    analysis = svc.new_analysis((title or "").strip()[:200] or None)
    analysis.owner_hash = owner
    svc.add_document(db, analysis, extraction, digest, pipeline, provider is not None)
    return _detail(analysis, settings)


@router.post("/{analysis_id}/documents", response_model=AnalysisOut, status_code=201,
             dependencies=[Depends(rate_limit)])
async def add_document(analysis_id: str, file: UploadFile = File(...), settings: Settings = Depends(get_settings),
                       db: Session = Depends(get_db),
                       provider: Optional[AIProvider] = Depends(get_ai_provider),
                          owner: str = Depends(workspace_owner)) -> AnalysisOut:
    analysis = _load(db, analysis_id, owner)
    extraction, digest, pipeline = await _process(file, settings, provider)
    try:
        svc.add_document(db, analysis, extraction, digest, pipeline, provider is not None)
    except svc.DuplicateDocument:
        raise _err(409, "duplicate_document", "This exact document has already been added to this analysis.")
    db.refresh(analysis)
    return _detail(analysis, settings)


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> list[AnalysisSummary]:
    from sqlalchemy import select
    from app.db.models import Analysis
    rows = db.scalars(select(Analysis).where(Analysis.owner_hash == owner).order_by(Analysis.created_at.desc())).all()
    return [AnalysisSummary(id=a.id, title=a.title, institution=a.institution, programme=a.programme,
                            academic_year=a.academic_year, document_count=len(a.documents),
                            created_at=a.created_at) for a in rows]


def _load(db: Session, analysis_id: str, owner: str):
    try:
        analysis = svc.get_analysis(db, analysis_id)
        if not analysis.owner_hash or not hmac.compare_digest(analysis.owner_hash, owner):
            raise svc.NotFound("analysis")
        return analysis
    except svc.NotFound:
        raise _err(404, "not_found", "Analysis not found.")


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: str, settings: Settings = Depends(get_settings),
                 db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> AnalysisOut:
    return _detail(_load(db, analysis_id, owner), settings)


@router.patch("/{analysis_id}", response_model=AnalysisOut)
def patch_analysis(analysis_id: str, body: AnalysisPatch, settings: Settings = Depends(get_settings),
                   db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> AnalysisOut:
    analysis = _load(db, analysis_id, owner)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(analysis, key, value or None)
    db.commit()
    return _detail(analysis, settings)


@router.patch("/{analysis_id}/items/{item_id}", response_model=AnalysisOut)
def patch_item(analysis_id: str, item_id: str, body: ItemPatch, settings: Settings = Depends(get_settings),
               db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> AnalysisOut:
    analysis = _load(db, analysis_id, owner)
    try:
        svc.edit_item(db, analysis, item_id, body.model_dump(exclude_unset=True))
    except svc.NotFound:
        raise _err(404, "not_found", "Item not found.")
    except svc.InvalidEdit as exc:
        raise _err(422, "invalid_edit", exc.message)
    db.refresh(analysis)
    return _detail(analysis, settings)


@router.post("/{analysis_id}/conflicts/resolve", response_model=AnalysisOut)
def resolve(analysis_id: str, body: ConflictResolveIn, settings: Settings = Depends(get_settings),
            db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> AnalysisOut:
    analysis = _load(db, analysis_id, owner)
    try:
        svc.resolve_conflict(db, analysis, body.conflict_key, body.chosen_item_id, body.note)
    except svc.NotFound:
        raise _err(404, "not_found", "Conflict not found.")
    except svc.InvalidEdit as exc:
        raise _err(422, "invalid_resolution", exc.message)
    db.refresh(analysis)
    return _detail(analysis, settings)


@router.get("/{analysis_id}/documents/{document_id}/pages/{number}", response_model=PageTextOut)
def page_text(analysis_id: str, document_id: str, number: int, db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> PageTextOut:
    analysis = _load(db, analysis_id, owner)
    doc = next((d for d in analysis.documents if d.id == document_id), None)
    page = next((p for p in (doc.pages if doc else []) if p.number == number), None)
    if page is None:
        raise _err(404, "not_found", "Page not found.")
    return PageTextOut(number=page.number, text=page.text)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> None:
    """Permanently deletes the analysis, its documents' text, items and decisions."""
    analysis = _load(db, analysis_id, owner)
    db.delete(analysis)
    db.commit()


@router.post("/{analysis_id}/journey", response_model=JourneyOut)
def preview_journey(analysis_id: str, body: Optional[JourneyPreviewIn] = None,
                    db: Session = Depends(get_db), owner: str = Depends(workspace_owner)) -> JourneyOut:
    """PREVIEW ONLY. Builds a journey from the reviewed items. Nothing is saved and no AI is called.

    Blocked (409) while conflicts are unresolved, or while there is nothing reviewed to build from.
    """
    analysis = _load(db, analysis_id, owner)
    body = body or JourneyPreviewIn()
    try:
        journey = journey_service.build_preview(analysis, body.outcome, body.completed)
    except JourneyBlocked as exc:
        raise HTTPException(409, {"code": exc.code, "message": exc.message, "details": exc.details})
    return JourneyOut.model_validate(dataclasses.asdict(journey))
