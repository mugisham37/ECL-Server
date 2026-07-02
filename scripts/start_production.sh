#!/bin/bash
set -e

echo "Running database migrations..."
.venv/bin/alembic upgrade head

echo "Creating runtime directories..."
mkdir -p run

echo "Starting API + worker (honcho)..."
exec .venv/bin/honcho start -f Procfile.prod
