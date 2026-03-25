.PHONY: help dev up down build test test-unit test-frontend test-integration lint lint-fix format typecheck migrate migrate-create clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start full local stack (build + run all services)
	docker compose up --build -d
	@echo "Services starting... API: http://localhost:8000  Frontend: http://localhost:3000"
	docker compose logs -f api frontend

up: ## Start infrastructure only (postgres, milvus, redis)
	docker compose up -d postgres milvus redis

down: ## Stop all containers
	docker compose down

build: ## Build all Docker images
	docker compose build

test: test-unit test-frontend ## Run all tests

test-unit: ## Run backend unit tests
	uv run pytest tests/unit/ -q

test-frontend: ## Run frontend tests
	cd frontend && npx vitest run

test-integration: ## Run integration tests (requires infra running)
	uv run pytest tests/integration/ -v --tb=short

test-e2e: ## Run E2E tests in isolated Docker environment
	docker compose -f docker-compose.test.yml up --build -d
	@echo "Waiting for services to be healthy..."
	@sleep 15
	@echo "E2E test environment ready. Run Playwright tests manually."

lint: ## Run all linters
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/ --ignore-missing-imports
	cd frontend && npm run lint

lint-fix: ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

format: ## Format all code
	uv run ruff format src/ tests/
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,json}"

typecheck: ## Run mypy type checking
	uv run mypy src/ --ignore-missing-imports

migrate: ## Run database migrations
	uv run alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="description")
	uv run alembic revision --autogenerate -m "$(msg)"

clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	cd frontend && rm -rf .next node_modules/.cache
