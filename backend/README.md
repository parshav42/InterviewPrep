# InterviewAI backend

FastAPI backend for the existing vanilla frontend. PostgreSQL and S3-compatible storage are the production targets. Development defaults to SQLite and a private local object-storage adapter so the API can be tested without infrastructure.

## Local API

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8002
```

OpenAPI is available at `http://127.0.0.1:8002/docs`. Run tests with `.venv/bin/pytest -q`.

Serve the frontend locally from the repository root with `python3 -m http.server 5500`; it uses `http://127.0.0.1:8002/api` by default.

## Docker

From the repository root, run `docker compose -f backend/docker-compose.yml up --build`. The API and frontend are available at `http://127.0.0.1:8002`; Postgres is exposed on `5432`. Alembic migrations run inside the backend container before Uvicorn starts. MinIO is optional because the default stack uses private local storage; enable it with `docker compose -f backend/docker-compose.yml --profile storage up --build` only when the MinIO image is available in the registry.

## Verification

```bash
cd backend && .venv/bin/pytest -q
cd .. && find . -path './backend/.venv' -prune -o -path './node_modules' -prune -o -name '*.js' -print0 | xargs -0 -n1 node --check
npm install
npx playwright install chromium
npm run e2e
```

The Playwright suite launches Chromium with fake camera and microphone flags. Manual hardware verification still requires a browser with camera and microphone permissions: start the frontend and API, register and verify a user, upload a PDF, start an interview, confirm TTS speaks, confirm STT begins after TTS ends, speak a response, and confirm silence submits it. Test camera denial, microphone denial, TTS failure, STT failure, timer expiry, and reload persistence separately.

## Production checklist

- Use a secret manager for `DATABASE_URL`, `JWT_SECRET`, provider tokens, and storage credentials; never commit `.env`.
- Use `APP_ENV=production` with a non-default JWT secret and an explicit non-wildcard `CORS_ORIGINS` list.
- Put the API behind HTTPS so HSTS is meaningful, and use shared rate limiting such as Redis for multiple backend instances.
- Back up PostgreSQL before applying migrations and run `alembic upgrade head` during deployment.
- Configure S3/MinIO credentials and verify private object access, retention, and deletion.
- Replace the development email-verification console logger with a transactional email provider.

For PostgreSQL, set `DATABASE_URL` in an ignored `.env` and run `docker compose up --build`. The default Compose stack uses private local storage because the public MinIO image is unavailable in the current registry environment. To enable MinIO in an environment where the image is reachable, run `docker compose --profile storage up --build` and configure the storage credentials. Never put real JWT, database, LLM, or storage secrets in source control.

## Frontend connection

The existing frontend loads `js/api.js`. Set `window.INTERVIEW_API_BASE` before the module loads if the API is not at port 8002. Authenticated users can store the JWT returned by `/api/auth/register` or `/api/auth/login`; the existing resume and interview workflow then uses the REST APIs automatically. Without a token, the tested prototype mock flow remains available.

## Security boundaries

- Passwords are Argon2-hashed and JWTs carry only the user ID.
- User-facing queries always scope by the authenticated user ID.
- Admin routes depend on the `ADMIN` role and record protected user-detail views in `admin_audit_logs`.
- Resume files use generated private keys and are never served as public URLs.
- Analytics metadata drops known credential and private-content keys.
- Audio providers are interfaces and raw audio is not persisted by default.
- LLM rate limiting is process-local development protection only; production multi-instance deployments must put this limit behind a shared store such as Redis.
- Registration logs a 24-hour email-verification token in development. Call `POST /api/auth/verify-email?token=...` with that token; production deployments must replace the console logger with a transactional email provider before requiring verification for access.

The LLM and voice services currently use explicit development adapters/protocols. Configure provider adapters and S3-compatible storage before production deployment. When `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, and `STORAGE_SECRET_KEY` are set, private resume objects use S3/MinIO; otherwise development falls back to `STORAGE_LOCAL_ROOT`.
