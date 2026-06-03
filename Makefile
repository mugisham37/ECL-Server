.PHONY: help up down logs shell migrate migrate-down test test-cov lint type-check \
        format security-scan generate-keys seed-admin seed-dev clean

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

security-scan: ## Bandit SAST
	bandit -r app/ -ll

generate-keys: ## Generate RSA JWT keys
	python scripts/generate_keys.py

seed-admin: ## Seed platform superadmin
	python scripts/seed_superadmin.py

seed-dev: ## Seed dev data
	python scripts/seed_dev_data.py

clean: ## Remove caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
