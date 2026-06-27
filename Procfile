web:    bash scripts/start_production.sh
api:    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
worker: .venv/bin/celery -A app.tasks.celery_app worker --beat --loglevel=info --concurrency=4 -n worker@%h --schedule=run/celerybeat-schedule
