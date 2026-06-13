.PHONY: help up down logs shell migrate migrate-down test test-cov lint type-check \
        format security-scan generate-keys seed-admin seed-dev clean worker worker-beat dev-all

GIT_COMMIT = git -c user.email=dev@eclplatform.com -c user.name="ECL Developer" commit

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start postgres and redis
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop services
	docker compose -f docker/docker-compose.yml down

logs: ## Follow docker logs
	docker compose -f docker/docker-compose.yml logs -f

shell: ## Open psql shell
	docker compose -f docker/docker-compose.yml exec postgres psql -U ecl ecl_db

migrate: ## Apply migrations
	alembic upgrade head

migrate-down: ## Rollback one migration
	alembic downgrade -1

migrate-new: ## New migration (MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

test: ## Run tests
	pytest tests/ -v --tb=short

test-cov: ## Tests with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing

test-auth: ## Auth tests only
	pytest tests/test_auth/ -v

lint: ## Ruff check
	ruff check app/ tests/

format: ## Ruff format
	ruff format app/ tests/

type-check: ## Mypy strict
	mypy app/

security-scan: ## Bandit SAST + pip-audit dependency CVE scan
	bandit -r app/ -ll
	pip-audit --desc

generate-keys: ## Generate RSA JWT keys
	python scripts/generate_keys.py

seed-admin: ## Seed platform superadmin
	python scripts/seed_superadmin.py

seed-dev: ## Seed dev data
	python scripts/seed_dev_data.py

worker: ## Start Celery worker — REQUIRED for email delivery AND ECL compute
	celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

worker-beat: ## Start Celery worker + beat scheduler (periodic cleanup tasks)
	celery -A app.tasks.celery_app worker --beat --loglevel=info --concurrency=4

dev: ## Show commands to start all dev services (run each in a separate terminal)
	@echo ""
	@echo "  Terminal 1 (infrastructure):  make up"
	@echo "  Terminal 2 (api):             uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
	@echo "  Terminal 3 (worker):          make worker"
	@echo ""
	@echo "  The Celery worker is REQUIRED for:"
	@echo "    - Email delivery (signup, invites, password reset)"
	@echo "    - ECL compute (PD / LGD / EAD / ECL engines)"
	@echo "  Without it: emails are not sent AND compute stays stuck at 0%."
	@echo ""

dev-all: ## Start API + Celery worker+beat together (requires: make up first)
	honcho start

dev-check: ## Verify Redis is reachable on the configured Celery broker port
	@.venv/bin/python -c "from app.config import get_settings; import redis; s=get_settings(); r=redis.from_url(s.redis_celery_url); r.ping(); print('Redis OK:', s.redis_celery_url)"

clean: ## Remove caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
