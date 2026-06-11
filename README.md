# ECL-Server

Production FastAPI authentication backend for the ECL Platform.

## Quick start

```bash
cd ECL-Server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make generate-keys   # paste keys into .env
make up
createdb -h localhost -U ecl ecl_test_db  # or via docker
make migrate
```

### Development stack (email delivery requires all three)

Run each command in a **separate terminal**:

```bash
make up                                                          # Terminal 1: Postgres + Redis
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload        # Terminal 2: API
make worker                                                      # Terminal 3: Celery worker (required for emails)
```

Verify Redis is reachable: `make dev-check`

Email troubleshooting guide: [docs/EMAIL_DIAGNOSIS_PROMPT.md](docs/EMAIL_DIAGNOSIS_PROMPT.md)

Live SMTP smoke test: `pytest tests/test_email_smoke.py -m smtp -v`

## Tests

```bash
docker compose -f docker/docker-compose.test.yml up -d
pytest tests/ -v
```

## Frontend contract

Read-only reference: `../ECL-Web/`. Full spec: `ECL_AUTH_BACKEND_PROMPT.md`.
