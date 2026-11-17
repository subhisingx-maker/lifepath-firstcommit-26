# Windows setup (beginner friendly)

You need two programs: **Python 3.11** (for the backend) and **Node.js 20 or newer** (for the frontend, which
arrives in Phase 4). Python is enough to run everything built so far.

> These steps were written for Windows 10/11 and could not be run on a Windows machine while this was built.
> If a step behaves differently, tell me the exact message and I will fix the instructions.

## 1. Check what you already have

Open **PowerShell** (Start menu, type "PowerShell") and run:

```powershell
py -3.11 --version
python --version
node --version
npm --version
```

* Python must print `Python 3.11.x` (3.12 usually works too, but 3.11 is the tested target).
* Node must print `v20.x.x` or higher. npm prints a number such as `10.x.x`.
* A message like "not recognized" or "Python was not found" means it is not installed yet.

## 2. Install Python 3.11

**Easiest (winget, built into Windows 11 and recent Windows 10):**

```powershell
winget install --id Python.Python.3.11 -e
```

**Or manually:** download "Python 3.11.x" from https://www.python.org/downloads/windows/, run the installer and
**tick "Add python.exe to PATH"** on the first screen before clicking Install.

**Close PowerShell and open a new one**, then check:

```powershell
py -3.11 --version
```

Tip: if `python` opens the Microsoft Store, go to Settings > Apps > Advanced app settings > App execution aliases
and turn off the two "python" aliases. Using `py -3.11` avoids this problem.

## 3. Install Node.js 20 or newer

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

Or download the **LTS** installer from https://nodejs.org (any LTS version 20 or higher is fine) and accept the
defaults. Open a **new** PowerShell and check:

```powershell
node --version
npm --version
```

## 4. Run the backend (demo mode, no API key needed)

```powershell
cd path\to\lifepath\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload
```

If activation says "running scripts is disabled", run this once, then try activation again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then open these in your browser:

* http://127.0.0.1:8000/docs - interactive API page (try **POST /api/documents/extract** with a PDF from
  `sample_notices\`)
* http://127.0.0.1:8000/api/health - should show `"ai_mode": "demo"`
* http://127.0.0.1:8000/api/demo/journey - the fictional Demo National University journey

Stop the server with `Ctrl + C`.

## 5. Run the tests

With the virtual environment still active (you see `(.venv)` at the start of the prompt), in `backend\`:

```powershell
pytest -v
```

## 6. Adding your Gemini key later

1. Open `backend\.env` in Notepad or VS Code.
2. Paste your key after `GEMINI_API_KEY=` (no quotes, no spaces), then save.
3. Restart `uvicorn`. `/api/health` will now show `"ai_mode": "live"`.

Never share `.env` or paste the key into chat, code, or GitHub.

## 7. Frontend (available from Phase 4)

```powershell
cd path\to\lifepath\frontend
npm install
npm run dev
```

The `frontend` folder is empty until Phase 4.
