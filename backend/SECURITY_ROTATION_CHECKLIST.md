# Credential Rotation Checklist

The local secret-bearing `backend/.env` was removed. Use `backend/.env.example` as the only committed configuration template. Do not copy real values into tracked files.

Rotate these credentials at their issuing service before deploying:

- `DATABASE_URL`: rotate the database user's password at the PostgreSQL/Supabase provider, then update the deployment secret that supplies the full connection URL.
- `JWT_SECRET`: generate a new long random signing secret in the deployment secret manager. Rotating it invalidates existing access tokens.
- `HF_TOKEN`: revoke and recreate the Hugging Face access token at the Hugging Face account settings, then update the backend runtime secret.
- `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY`: rotate the MinIO/S3 access key pair in the object-storage service, then update the backend runtime secrets.
- `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`: rotate the MinIO administrator credentials in the Compose or deployment secret store; never use the example values in production.
- `LLM_API_KEY`, `SPEECH_API_KEY`, and `TTS_API_KEY`: revoke and recreate each provider key at its provider dashboard if the corresponding integration is enabled, then update runtime secrets.

Validation after rotation:

1. Confirm the old database, provider, JWT, and storage credentials are revoked.
2. Set replacement values through the runtime secret manager or an ignored local `.env`.
3. Start the backend and verify `/health` and `/health/llm` without logging configuration values.
4. Re-run authentication, resume storage, and interview smoke tests.

Repository limitation: this workspace contains no `.git` directory, so tracked-file status and Git-history secret scanning cannot be verified here. Run the following from the actual Git checkout before publishing:

```bash
git ls-files | grep -E '(^|/)(\.env|\.env\.|.*\.env$)'
git log --all -G '(JWT_SECRET|HF_TOKEN|DATABASE_URL|MINIO|API_KEY|PASSWORD)' --format='%H' -- . ':!backend/tests'
```