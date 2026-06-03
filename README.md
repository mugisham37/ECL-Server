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
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
docker compose -f docker/docker-compose.test.yml up -d
pytest tests/ -v
```

## Frontend contract

Read-only reference: `../ECL-Web/`. Full spec: `ECL_AUTH_BACKEND_PROMPT.md`.
