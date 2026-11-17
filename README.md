# LIFEPATH - From confusion to completion

Turns admission notices into clear, source-backed, step-by-step journeys. This repository is being migrated from a
single-file prototype (`legacy/LIFEPATH.html`, kept for recovery) to React + FastAPI. See `docs/CHECKLIST.md` for
what is done and what is pending.

## Current status: React frontend + FastAPI backend + journey preview

Works without an API key (demo mode): PDF text extraction by page, scanned/corrupt/oversized file handling,
deterministic date detection, the fictional demo journey API, draft analyses stored in SQLite, four fictional
sample PDFs.

With `GEMINI_API_KEY` set: the AI proposes requirements (eligibility, documents, deadlines, stages, pathways).
Every proposed quote is re-checked against the real document text, dates come from the deterministic parser, and
conflicts between documents are flagged for a person to resolve. The live Gemini call has not been run yet.

Journey preview: reviewed items become steps with dependencies and selected / waitlisted / not-selected branches.
It is a preview only (not saved) and uses no AI. The React frontend is in `lifepath frontend/` and uses the
fictional demo endpoint by default; uploaded notices use the analysis and journey-preview endpoints.

Not built yet: saved journeys and progress, personalised applicability, RAG assistant, OCR, migrations, and
production authentication. Without Gemini credentials, uploads can be extracted and stored but do not yield
AI-proposed requirements; use the clearly labelled fictional demo for a complete no-key walkthrough.

## Quick start (backend)

Windows users: follow `docs/WINDOWS_SETUP.md` (includes installing Python 3.11 and Node 20+).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs. `GET /api/health` reports `"ai_mode": "demo"` until `GEMINI_API_KEY` is set in
`backend/.env`.

## Quick start (frontend)

```bash
cd "lifepath frontend"
npm ci
npm run dev
```

The local frontend defaults to `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` in a local `.env` file only when
you want to use a different API. In production, requests go directly to the Render API so long-running notice analysis
does not hit Netlify's proxy timeout. The backend allows the existing Netlify site origin; change that allowlist if the
site's domain changes.

## Deploy

The root `netlify.toml` sets Netlify's base directory to `lifepath frontend`, installs from the checked-in lockfile,
builds with `npm run build`, publishes `dist`, and keeps an `/api/*` proxy for simple requests. Connect the existing
GitHub repository to Netlify and use the `master` branch; these settings should be detected from the file. No
frontend secret or dashboard change is needed for API routing. Keep `GEMINI_API_KEY` in Render's
environment settings only; never put it in GitHub or the frontend. Without a Gemini key, the bundled fictional demo
still works; notice upload will not create extracted requirements or a journey.

## Fictional end-to-end demo

Open the deployed frontend, choose **Upload notice**, and select
`sample_notices/01_demo_national_university_bsc_2027-28.pdf`. It is explicitly fictional. In demo mode the PDF text
can be extracted and stored, but journey generation from uploaded notices requires Gemini. The complete, no-key
journey walkthrough is loaded from `GET /api/demo/journey`; confirm the **Demo data** banner and verify dates and
quotes against the fictional PDF. Never present this sample as an official university notice.

## Endpoints so far

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Mode (demo/live), OCR status, version. Never returns the key. |
| GET | `/api/demo/journey` | Fictional Demo National University journey with source page + exact quote on every item. |
| POST | `/api/documents/extract` | Upload a PDF: page-by-page text, scanned/blank/failed page report, dates with page numbers and review flags. Nothing is saved. |
| POST | `/api/analyses` | Upload the first notice. Creates a draft only if processing succeeds (no empty drafts). |
| POST | `/api/analyses/{id}/documents` | Add another notice (e.g. a corrigendum). Exact duplicates are rejected (409). |
| GET | `/api/analyses`, `/api/analyses/{id}` | List drafts / full review view: items, conflicts, not-found topics, counts. |
| PATCH | `/api/analyses/{id}` | Edit title, institution, programme, academic year. |
| PATCH | `/api/analyses/{id}/items/{item_id}` | Correct an item (name, explanation, level, condition, date) or accept/reject it. Quote and page cannot be edited. |
| POST | `/api/analyses/{id}/conflicts/resolve` | Record YOUR decision on a conflict. |
| GET | `/api/analyses/{id}/documents/{doc}/pages/{n}` | Stored text of one page. |
| POST | `/api/analyses/{id}/journey` | **Preview** a journey from reviewed items (optional `outcome`, `completed`). Nothing saved, no AI. Blocked while conflicts are unresolved. See `docs/JOURNEY_ENGINE.md`. |
| DELETE | `/api/analyses/{id}` | Permanently delete the draft and all stored text. |

## Troubleshooting: Gemini errors during upload
Transient network, Gemini HTTP 429, and 5xx failures are retried up to three times with exponential backoff. The client
honours `Retry-After` when Gemini supplies it, and will not wait past `AI_TIMEOUT_SECONDS` for one provider request.
The extraction pipeline handles a timed-out or truncated batch by splitting it once into smaller halves, then uses
smaller batches for later pages. Retries are not repeated in both layers.

If a provider remains unavailable after its retries, an upload with earlier successful batches is saved as a
partial analysis with a warning naming pages that were not analysed. If no batch succeeded, the API returns the
specific provider error, including its HTTP status and a safe provider diagnostic when available. A timeout is
reported as HTTP 504. You can lower `AI_BATCH_CHARS` (for example to 12000) to reduce the size of each request.

## Tests

```bash
cd backend && pytest -v        # or:  python -m unittest discover -s tests -t . -v
```

Tests that need PyMuPDF/FastAPI are skipped (and reported as skipped) if those packages are missing.

## Layout

```
legacy/LIFEPATH.html        original prototype (unchanged)
sample_notices/             4 fictional PDFs + README describing each scenario
backend/app/core/           settings (.env loading)
backend/app/services/       pdf_extractor, deadline_parser, ai_service, gemini_provider, prompt_builder,
                            extraction_pipeline, quote_verifier, conflict_detector, analysis_service, rate_limiter,
                            journey_engine, journey_service
backend/app/api, schemas/   routes and response models
backend/app/db/             SQLAlchemy models and session
backend/app/data/           demo_journey.json
backend/scripts/            generate_sample_notices.py
backend/tests/              tests and fixtures
docs/                       WINDOWS_SETUP.md, CHECKLIST.md
frontend/                   empty until Phase 4
```

## Privacy (accurate for this phase)

* Stored on this server in a local SQLite file (`backend/lifepath.db`): the TEXT of the notices you upload, the
  extracted items, and your review decisions. The PDF file itself is not stored. Delete a draft with
  `DELETE /api/analyses/{id}`.
* With no `GEMINI_API_KEY` (demo mode) nothing is sent to any AI service.
* With a key, the text of each uploaded notice is sent to Google's Gemini API to be analysed. Do not upload documents
  you are not comfortable sending there. Notice text is not written to logs.
* There is no login yet: anyone who can reach the API can read every draft. Run it only on your own machine until
  authentication is added.
