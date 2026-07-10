.DEFAULT_GOAL := help
SOURCES := shared/ backend/ frontend/

# ── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo ""
	@echo "NBA Rookie Dashboard — available commands:"
	@echo ""
	@echo "  Setup"
	@echo "    make install        Install dependencies (poetry install)"
	@echo "    make install-dev    Install with dev dependencies"
	@echo ""
	@echo "  Run"
	@echo "    make dev            Docker Compose up (full stack)"
	@echo "    make down           Docker Compose down"
	@echo "    make logs           Logs for all Docker services"
	@echo "    make logs-api       Logs for API service only"
	@echo ""
	@echo "  Format"
	@echo "    make format         Format code (docformatter + black)"
	@echo "    make format-check   Check formatting without changes"
	@echo ""
	@echo "  Quality"
	@echo "    make lint           Lint (ruff)"
	@echo "    make typecheck      Type check (mypy)"
	@echo "    make check          format-check + lint + typecheck"
	@echo ""
	@echo "  Tests"
	@echo "    make test           All tests (pytest)"
	@echo "    make test-unit      Unit tests only"
	@echo "    make test-int       Integration tests only"
	@echo "    make test-cov       Tests with coverage report"
	@echo ""
	@echo "  AI Evaluation"
	@echo "    make eval           Run eval on golden dataset"
	@echo ""
	@echo "  Database"
	@echo "    make db-migrate     Run Alembic migrations"
	@echo "    make db-shell       Connect to PostgreSQL (psql)"
	@echo ""

# ── Setup ────────────────────────────────────────────────────────────────────

.PHONY: install
install:
	poetry install

.PHONY: install-dev
install-dev:
	poetry install --with dev

# ── Run ──────────────────────────────────────────────────────────────────────

.PHONY: dev
dev:
	docker compose up

.PHONY: dev-build
dev-build:
	docker compose up --build

.PHONY: down
down:
	docker compose down

.PHONY: down-volumes
down-volumes:
	docker compose down -v

.PHONY: logs
logs:
	docker compose logs -f

.PHONY: logs-api
logs-api:
	docker compose logs -f api

# ── Format ───────────────────────────────────────────────────────────────────

.PHONY: format
format:
	-poetry run docformatter -r -i $(SOURCES)
	poetry run ruff check --select I --fix $(SOURCES)
	poetry run black $(SOURCES)

.PHONY: format-check
format-check:
	-poetry run docformatter -r --check $(SOURCES)
	poetry run ruff check --select I $(SOURCES)
	poetry run black --check $(SOURCES)

# ── Quality ──────────────────────────────────────────────────────────────────

.PHONY: lint
lint:
	poetry run ruff check $(SOURCES)

.PHONY: lint-fix
lint-fix:
	poetry run ruff check --fix $(SOURCES)

.PHONY: typecheck
typecheck:
	poetry run mypy $(SOURCES)

.PHONY: check
check: format-check lint typecheck

# ── Tests ────────────────────────────────────────────────────────────────────

.PHONY: test
test:
	poetry run pytest

.PHONY: test-unit
test-unit:
	poetry run pytest tests/unit/

.PHONY: test-int
test-int:
	poetry run pytest tests/integration/

.PHONY: test-cov
test-cov:
	poetry run pytest --cov=$(SOURCES) --cov-report=term-missing --cov-report=html

# ── AI Evaluation ────────────────────────────────────────────────────────────

.PHONY: eval
eval:
	poetry run python evals/run_eval.py

# ── LangSmith ────────────────────────────────────────────────────────────────

.PHONY: verify-langsmith
verify-langsmith:
	docker compose exec api python -m backend.core.langsmith_verify

# ── Database ─────────────────────────────────────────────────────────────────

.PHONY: db-migrate
db-migrate:
	docker compose exec api alembic upgrade head

.PHONY: db-shell
db-shell:
	docker compose exec postgres psql -U postgres -d nba_rookie_dashboard
