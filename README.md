# InterviewAI

This project is a vanilla HTML/CSS/JS frontend with a FastAPI backend and PostgreSQL/SQLite-backed interview workflow. The browser flow is a voice interview: the AI asks a question, the browser speaks it with TTS, the microphone captures the answer, silence triggers auto-submit, and the backend evaluates the response.

## Local development

1. Start the API:
   ```bash
   cd backend
   cp .env.example .env
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   .venv/bin/alembic upgrade head
   .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
   ```
2. Serve the frontend:
   ```bash
   cd ..
   python3 -m http.server 5500
   ```
3. Open http://127.0.0.1:5500/index.html

## Docker

```bash
cd backend
docker compose -f docker-compose.yml up --build
```

The API listens on http://127.0.0.1:8002 and the frontend is served by the API itself at the same host root. The Postgres container is exposed on 5432. The default stack uses local/private storage unless MinIO is explicitly enabled with the storage profile.

## Health checks

- http://127.0.0.1:8002/health
- http://127.0.0.1:8002/health/llm
- http://127.0.0.1:8002/

## Browser media flow

- Camera requests use a separate `getUserMedia({ video: true, audio: false })` stream.
- Microphone requests use `getUserMedia({ audio: true, video: false })`.
- TTS waits for `speechSynthesis` and only starts listening after the utterance ends.
- STT uses `SpeechRecognition`/`webkitSpeechRecognition` with `continuous` and `interimResults` enabled.
- Silence detection auto-submits when a non-empty final transcript remains silent for 2.5s.
- If TTS or STT is unavailable, text fallback UI is shown without blocking the interview.

Browser speech is the preferred production voice path: the live interview uses the browser's native TTS and STT APIs directly. The authenticated backend `/api/voice/transcribe` and `/api/voice/synthesize` adapters are deterministic local fallbacks for environments that need server-side audio handling; they are not external speech-provider integrations.

## Verification commands

```bash
cd backend && .venv/bin/pytest -q
find . -path './backend/.venv' -prune -o -path './node_modules' -prune -o -name '*.js' -print0 | xargs -0 -n1 node --check
npm run e2e
docker compose -f backend/docker-compose.yml config -q
```

## Manual hardware test

See [docs/MANUAL_VOICE_TEST.md](docs/MANUAL_VOICE_TEST.md) for full Chrome-on-device verification instructions.

## Production notes

- Keep secrets in a local `.env` file only; do not commit it.
- Set a real `JWT_SECRET` and explicit `CORS_ORIGINS` when `APP_ENV=production`.
- Do not rely on `development-only-change-me` values in production.
- Rate limiting is process-local in development; a shared store such as Redis is required for multi-instance deployments.

