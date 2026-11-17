# Progress checklist

Legend: [x] done and tested here, [~] written but NOT executed in the build sandbox, [ ] pending.

## Phase 0 - skeleton
- [x] Folder structure, `legacy/` backup of the prototype
- [x] `.gitignore`, `.env.example`, requirements files, `pytest.ini`
- [x] Windows setup guide (written, not run on Windows)
- [x] README

## Phase 1 - backend foundations
- [x] Settings loader: demo mode without key, `.env` on Windows (BOM, CRLF), key never in repr (10 tests run)
- [x] AI status service (demo/live) (2 tests run)
- [x] Deterministic date parser, prototype regex bug (#1) fixed and regression-tested (20 tests run)
- [x] Upload validation, page analysis (scanned / blank / failed), safe filenames (13 tests run)
- [x] 4 fictional sample PDFs + scanned and corrupted fixtures; page counts verified
- [x] Demo journey JSON: all 19 source quotes verified against the PDF text (checked with pdfplumber)
- [~] PyMuPDF extraction (`extract_pdf`) - code written; its 7 tests are SKIPPED here (PyMuPDF not installable offline)
- [~] FastAPI app and 3 endpoints - 5 API tests SKIPPED here (FastAPI not installable offline)
- [x] Database models (moved from Phase 1 to Phase 2; migrations still pending)
- [x] Rate limiting on upload endpoints (in memory, one process; see README)

## Phase 1 validation (by you, on Windows)
- [x] 55 tests passed, API started, /api/health = demo, sample PDF extracted (reported by you)

## Phase 2 - AI extraction and review
Legend for this phase: [x] executed here, [~] written, tests SKIPPED in the build sandbox (needs pydantic / SQLAlchemy / FastAPI / PyMuPDF, run them on your laptop)
- [x] Quote verifier: exact / corrected page / near-match / invented / too short / ellipsis (12 tests run)
- [x] Conflict detector: deadlines and document requirements, shows every side (9 tests run)
- [x] Prompt builder: nonce-delimited untrusted document, page markers, batching (4 tests run)
- [x] Gemini client: key in header only, error mapping, truncated/blocked replies (via a fake transport, 7 tests run)
- [x] JSON reply parser, rate limiter (6 tests run)
- [x] Config: DATABASE_URL, AI timeout, batch size, rate limit
- [~] Pydantic AI output schema + extraction pipeline (13 tests written, SKIPPED here)
- [~] SQLAlchemy models, session, analysis service (covered by the API tests, SKIPPED here)
- [~] /api/analyses endpoints: create, add document, list, get, edit header, edit item, resolve conflict, page text, delete (15 tests written, SKIPPED here)
- [ ] Live Gemini call has NEVER been run (no key, no network). Only the fake provider has been tested.
- [ ] Alembic migrations (deferred on purpose: tables are created automatically until the schema settles after Phase 3)
- [ ] Manual "add a missing item" in review
- [ ] Applicability filtering by student circumstances (Phase 3)

Review states: Verified against source / Unverified / Needs review / Not found / Conflict detected.
"Verified" means the quote is really in the document. The explanation next to it is always AI-written.
## Phase 3 - Journey engine, branches, next action, deadlines
Step B (preview) - [x] executed here, [~] written but tests SKIPPED in the sandbox
- [x] Pure-Python journey engine: usable-item rules, steps from templates, dependencies (notice vs general flow), loop protection, branches, statuses, progress, gaps, suggested steps (54 tests run, including the items below)
- [x] Conflict gate in the engine: unresolved conflicts block, chosen side excludes the others (5 tests)
- [x] Audit fix: a missing template step passes its dependencies on (transitively), so e.g. the merit-list step stays locked until registration and documents are done; also applies to selected / waitlisted / not-selected steps (14 regression and branch tests)
- [x] Editable step templates (`journey_templates.json`)
- [~] `journey_service` (DB rows -> engine), `schemas/journey.py`, `POST /api/analyses/{id}/journey` (9 API tests written, SKIPPED here)
- [ ] Saved journeys and persisted progress/outcome (Step C)
- [ ] Next-action recommender (Step C)
- [ ] Applicability filtering by student circumstances (category, domicile, ...)
- [ ] Verified against a REAL Gemini extraction (the engine has only seen hand-built and fake-AI items)
## Phase 4 - React/Vite/TypeScript/Tailwind/shadcn frontend shell  [ ]
## Phase 5 - Remaining screens, Ask LIFEPATH (RAG), export/delete  [ ]
## Phase 6 - Demo polish, Playwright, accessibility, security pass, deployment  [ ]

## Known limitations right now
- OCR is not implemented. Scanned PDFs are detected and reported, not read.
- Vague dates ("second week of August") are not parsed; they are simply not reported as dates yet.
- Date ranges are returned as two separate dates.
- Notice text is now stored in SQLite (page text, extracted items, your decisions). The PDF file itself is not.
- The rate limiter is per server process.
- Items cannot be added manually yet; wrong items can be edited or rejected.
- No frontend yet; use `/docs` to try the API.
