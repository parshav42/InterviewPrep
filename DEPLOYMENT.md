# InterviewAI Deployment

## Prerequisites

- Docker Engine and Compose v2
- A reachable PostgreSQL instance or the included Compose database
- HTTPS termination for production
- Provider credentials for the selected LLM and S3-compatible storage

## Environment

Copy `backend/.env.example` to an ignored `backend/.env` and set placeholders before deployment:

- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB`
- `JWT_SECRET=<long-random-secret>`
- `CORS_ORIGINS=["https://app.example.com"]`
- `LLM_PROVIDER=mock|huggingface|qwen_remote`
- `HF_TOKEN` or `LLM_BASE_URL` and `LLM_API_KEY`, as applicable
- `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, and `STORAGE_BUCKET`

Never commit real values.

### Voice path

The production interview flow prefers browser-native `speechSynthesis` and `SpeechRecognition`/`webkitSpeechRecognition`, so no speech-provider key is required for the main voice experience. Backend `/api/voice/transcribe` and `/api/voice/synthesize` use deterministic local adapters as fallbacks. Wire an external provider only when server-side audio processing is required.

## Commands

```bash
docker compose -f backend/docker-compose.yml config -q
docker compose -f backend/docker-compose.yml up --build -d
docker compose -f backend/docker-compose.yml ps
```

Migrations run before Uvicorn in the backend image. To inspect the migration head:

```bash
docker compose -f backend/docker-compose.yml exec backend alembic current
```

## Health checks

- `GET http://127.0.0.1:8002/` returns the InterviewAI frontend.
- `GET http://127.0.0.1:8002/health` returns `{"status":"ok","database":"ok"}`.
- `GET http://127.0.0.1:8002/health/llm` reports provider reachability.

Production must reject the development JWT secret and wildcard CORS. HSTS is emitted when `APP_ENV=production`; terminate TLS before the application.

## Manual voice check

Use Chrome on a laptop with a camera and microphone. Open the root URL, register, verify the email token, upload a valid PDF, create an interview, and enter the live view. Allow both permissions. Confirm the camera preview has a live image, the question is spoken, recognition begins after speech ends, the transcript appears, and two seconds of silence submits the answer and advances the question. End the interview and confirm final feedback renders. Repeat once with camera denied and once with microphone denied; the interview must continue with the corresponding fallback.

## Rollback

```bash
docker compose -f backend/docker-compose.yml down
git checkout <known-good-release>
docker compose -f backend/docker-compose.yml up --build -d
```

Restore the database from the latest verified backup if a migration rollback is required. Do not downgrade production schemas by deleting migration rows.
