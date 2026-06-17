api:    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
worker: celery -A app.tasks.celery_app worker --beat --loglevel=info --concurrency=4
