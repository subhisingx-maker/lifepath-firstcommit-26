# Real-user readiness work in progress

This hackathon build is not a production release. The public deployment must be checked separately.

## Implemented

- Starts with a notice upload rather than automatically loading fictional data.
- Uses a 256-bit per-browser workspace credential for analyses. The API stores only a SHA-256 hash and restricts listing, reading, modifying, and deleting analyses to the matching credential. Older unowned records are retained but cannot be accessed through these routes until a safe ownership migration is designed.
- Restores the browser's most recent analysis and its progress. Progress is stored in the browser, not in a user account or in the database.
- Displays extracted deadlines and eligibility rather than fixed demo dates and counts supported journey steps separately from suggestions.
- Accepts PostgreSQL connection URLs through DATABASE_URL with the psycopg driver.

## Critical work before production

1. Device credentials are not a complete account system: clearing browser storage or changing devices loses access, and there is no recovery. Implement and review an appropriate identity provider, secure account recovery, and authorization.
2. Provision a durable production database with backups and test it. The current Render free service stores SQLite on an ephemeral filesystem; the free Render Postgres plan expires after 30 days. Do not connect real users to that setup as durable storage.
3. Export and migrate any existing analyses safely before deploying this branch. Unowned legacy rows are preserved but intentionally inaccessible until a migration is completed. Do not deploy frontend and backend independently: the protected backend requires the matching frontend header and preflight configuration.
4. Perform a security review and end-to-end tests with real credentials, account recovery, database restarts and real notices. Test AI errors, OCR limitations, ambiguous dates, conflicting documents, and the full review workflow.
5. The AI service can return quota or temporary overload errors. Free hosting can sleep and is not suitable for a reliability promise. Always verify output against the official notice.

## Checks performed

202 backend unit and API integration tests passed. The Vite production build passed. A local browser test with a fictional notice and fake provider generated a journey, checked a supported step, and restored the progress after refresh. A deployed earlier version generated a fictional journey using Gemini after a transient 503, but this branch has not been verified with the live service or PostgreSQL.
