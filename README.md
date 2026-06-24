# ECL-Server

Production FastAPI authentication backend for the ECL Platform.

## Quick start

```bash
cd ECL-Server
make setup              # once: create .venv and install dependencies
cp .env.example .env    # once: configure environment
make generate-keys      # once: paste keys into .env
```

### Development (two terminals — separate logs)

**Terminal 1 — infrastructure + Celery:**

```bash
make dev
```

**Terminal 2 — API backend only:**

```bash
make api
```

Verify the API is healthy:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Stop everything when done:

```bash
make stop
```

Do **not** run bare `uvicorn` from your shell — it uses system Python and will fail with `ModuleNotFoundError: No module named 'fastapi'`. Always use `make api`.

### Combined logs (optional)

If you prefer API + Celery in one terminal (mixed logs):

```bash
make up && make migrate
make dev-all
```

Verify Redis is reachable: `make dev-check`

Email troubleshooting guide: [docs/EMAIL_DIAGNOSIS_PROMPT.md](docs/EMAIL_DIAGNOSIS_PROMPT.md)

Live SMTP smoke test: `make test` with `pytest tests/test_email_smoke.py -m smtp -v`

## Tests

```bash
docker compose -f docker/docker-compose.test.yml up -d
make test
```

## Frontend contract

Read-only reference: `../ECL-Web/`. Full spec: `ECL_AUTH_BACKEND_PROMPT.md`.
