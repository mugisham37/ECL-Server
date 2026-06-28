#!/bin/bash
set -e

echo "Starting Celery worker + beat..."
mkdir -p run
.venv/bin/celery \
  -A app.tasks.celery_app worker \
  --beat \
  --loglevel=info \
  --concurrency=2 \
  -n worker@%h \
  --schedule=run/celerybeat-schedule &

echo "Running database migrations..."
.venv/bin/alembic upgrade head

echo "Starting API server..."
exec .venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --no-access-log
