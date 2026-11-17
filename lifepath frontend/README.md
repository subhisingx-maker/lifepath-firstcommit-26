# LIFEPATH frontend

Responsive React + Vite frontend for the LIFEPATH hackathon demo. Team: Unscripted Minds · FirstCommit '26.

## Run on Windows

1. Install the current Node.js LTS release from [nodejs.org](https://nodejs.org/) if `node` and `npm` are not already available.
2. Open PowerShell in this folder (`LIFEPATH-frontend`).
3. Install packages and start Vite:

   ```powershell
   npm install
   npm run dev
   ```

4. Open the local address printed by Vite, usually `http://localhost:5173`.

To make a production bundle:

```powershell
npm run build
```

The optimized files are written to `dist`. To preview that bundle locally, run `npm run preview`.

## Connect to the existing FastAPI backend

Start the existing backend separately and leave its data and files in place. By default, this frontend requests:

```text
GET http://127.0.0.1:8000/api/demo/journey
```

To use another backend address, copy `.env.example` to `.env.local`, set the URL, then restart Vite:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

If the browser reports a CORS error, configure the existing FastAPI app to allow the frontend origin `http://localhost:5173` (and `http://127.0.0.1:5173` if you open Vite with that hostname). This is a setting in the existing backend; this project does not change backend files.

When the endpoint is unreachable, the UI shows a connection message and switches to its built-in fictional nine-step journey so you can still explore the screens. The top banner labels all such content as **DEMO MODE**. When the endpoint responds, the frontend displays its returned journey fields where recognized. The response adapter accepts common field names; if the backend uses a different response shape, update `normalizeJourney` in `src/App.jsx` to match its documented schema.

## Demo scope and limitations

- The only live backend request implemented here is `GET /api/demo/journey`.
- The notice picker currently selects a PDF locally to demonstrate the upload area. It does not upload the file or extract text.
- Real AI extraction is not configured and is not claimed by this frontend. Backend application creation is not wired to the UI.
- Step completion and the demo profile are stored in this browser's local storage; they do not update the backend.
- Dates and names in the fallback are fictional. Verify requirements and deadlines with the official university notice.
- The fallback content and branch actions are for demonstration only, not admissions advice.

## Project structure

```text
LIFEPATH-frontend/
├── index.html
├── package.json
├── vite.config.js
├── .env.example
└── src/
    ├── App.jsx
    ├── main.jsx
    └── styles.css
```
