# LIFEPATH deployment and hackathon submission

## What is included

- React + Vite frontend in `lifepath frontend/`.
- FastAPI backend in `backend/`.
- Fictional admission notices in `sample_notices/`.
- A clearly labelled, source-backed fictional demo journey available without an AI key.
- Netlify build settings in the root `netlify.toml`.

## Publish the frontend on Netlify

1. Connect the existing GitHub repository `subhisingx-maker/lifepath-firstcommit-26` to the existing Netlify site.
2. Deploy the `master` branch. Netlify reads the build base, install/build commands and publish directory from
   `netlify.toml`; do not set a second conflicting base directory in the UI.
3. Confirm the deploy log shows `npm ci`, `npm run build`, and a published `dist` directory.
4. Open the resulting `https://<site-name>.netlify.app` address and check that the overview displays a **Demo data**
   banner and the fictional Demo National University journey.

No API key belongs in Netlify. The frontend uses the deployed Render API by default. `VITE_API_BASE_URL` is only
needed if the backend URL changes.

## Frontend-to-backend connection

In production the frontend requests `/api/...` on its own Netlify origin. The `netlify.toml` rule proxies those
requests to the existing Render API, so browser CORS does not need to be enabled for the public Netlify origin.
Keep `GEMINI_API_KEY` in Render's secret environment settings only. Never add it to this repository or to Netlify.

## Verify the deployed connection

Open these addresses, replacing `<site-name>` with the actual Netlify site name:

- The existing Netlify site's public URL
- `https://lifepath-firstcommit-26.onrender.com/api/health`
- `https://lifepath-firstcommit-26.onrender.com/api/demo/journey`

The health response should contain `"status":"ok"`; its `ai_mode` is `demo` when no Gemini key is configured and
`live` when a real key is configured. The demo endpoint should contain `"fictional":true`, nine steps and an explicit
fictional-data warning. In the browser, the page should load this API data through the Netlify proxy without a
connection warning.

## Demonstrate a fictional notice

Use `sample_notices/01_demo_national_university_bsc_2027-28.pdf`. It is fictional and must never be described as an
official university notification. The API's PDF extraction endpoint can extract its four pages without AI. Building
a personalized journey from an uploaded notice requires a functioning Gemini API key on Render and human review of
the extracted items. Without that key, use the bundled demo journey for the complete presentation flow; do not imply
that upload produced AI analysis.

For a hackathon walkthrough:

1. Point out the **Demo data** banner and read the fictional warning.
2. Show eligibility, document checklist, deadlines and the nine-step journey.
3. Mark a step complete, then show how the journey progress changes.
4. Explain that uploaded notice extraction and the Gemini-assisted review path are separate from this no-key demo.
5. State that dates, university and admission rules are fictional and cite the included sample PDF.

## Local build checks

From `lifepath frontend/`, run `npm ci` then `npm run build`. From `backend/`, run
`python -m unittest discover -s tests -t . -v`. The API integration tests use Starlette's `TestClient`; if they stall
under the installed Starlette/httpx combination, run the non-API suite separately or verify endpoints through a local
Uvicorn server.

## Readiness statement

The source tree is ready for Netlify to build. Call the public website ready for submission only after Netlify reports
a successful deploy, the frontend loads the Render demo without CORS errors, and the team completes its live demo
rehearsal. A live Gemini-assisted uploaded-notice journey has not been verified in this delivery.
