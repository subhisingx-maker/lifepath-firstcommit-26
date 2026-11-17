# LIFEPATH hackathon deployment and submission

Public website: https://lifepath-firstcommit-26.netlify.app/
Backend: https://lifepath-firstcommit-26.onrender.com/

## Record a walkthrough

1. Open the public website. Enter a fictional name, age, education and optional category.
2. Choose one of the fictional PDFs in `sample_notices/` and select **Upload and analyse**.
3. Wait for the AI analysis, then show the notice explanation, personal checks, journey steps and source references. Clearly identify the sample notice as fictional.
4. Explain that students should verify the guidance against the official notice.

Only text-based PDFs are supported; scans requiring OCR are not. The free backend may take a minute to wake up and its local database can be cleared by a restart. The AI may refuse requests when quota is exhausted. Student profile details stay in the browser; notice text goes to Google Gemini and should not contain private personal information.

## Configuration

The existing `master` branch deploys to Netlify and Render. Netlify builds `lifepath frontend/` using the root `netlify.toml`. Set `GEMINI_API_KEY` and `GEMINI_MODEL` in Render's environment settings only; never commit credentials. The backend permits the existing Netlify origin and workspace-token header.

## Run locally

Run `python -m pip install -r requirements.txt` and `uvicorn app.main:app --reload` inside `backend/` with a valid Gemini key configured privately. In `lifepath frontend/`, run `npm ci` then `npm run dev`. For checks, run `python -m unittest discover -s tests -t . -q` inside `backend/` and `npm run build` inside the frontend directory.

This hackathon build is not a production service; see `docs/PRODUCTION_READINESS.md` before relying on it for real students.
