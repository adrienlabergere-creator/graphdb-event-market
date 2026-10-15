.PHONY: help venv install run docker-build docker-run docker-stop schema test lint format clean tree score score-md status status-md healthcheck

PY ?= python3
VENV ?= .venv
ACT = . $(VENV)/bin/activate

help:
	@echo "Commands:"
	@echo "  make venv          Create local virtualenv ($(VENV))"
	@echo "  make install       Install requirements into $(VENV)"
	@echo "  make run           Run FastAPI (uvicorn) on :8000 with reload"
	@echo "  make docker-build  Build the Docker images"
	@echo "  make docker-run    Start the full Docker Compose stack"
	@echo "  make docker-stop   Stop the Docker Compose stack"
	@echo "  make schema        Apply constraints and indexes to Neo4j"
	@echo "  make test          Run pytest with coverage"
	@echo "  make lint          Run pylint (score must stay >= 9.5)"
	@echo "  make format        Run black (line length 120)"
	@echo "  make status        Where the project stands (WHO=Firstname for your next task)"
	@echo "  make score         Check the grading checklist automatically"
	@echo "  make healthcheck   Call /health through the reverse proxy"
	@echo "  make clean         Remove caches and temp files"
	@echo "  make tree          Show project tree (depth 3)"

venv:
	@if [ ! -d "$(VENV)" ]; then \
	    $(PY) -m venv $(VENV); \
	    $(ACT) && pip install --upgrade pip; \
	    echo "Created $(VENV)"; \
	else echo "$(VENV) already exists"; fi
	@echo "To activate: source $(VENV)/bin/activate"

install: venv
	@$(ACT) && pip install -r requirements.txt

run:
	@$(ACT) && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker compose build

docker-run:
	docker compose up --build

docker-stop:
	docker compose down

schema:
	@$(ACT) && python -m scripts.apply_schema

test:
	@$(ACT) && pytest -q --cov=app --cov-report=term-missing --cov-report=xml

lint:
	@$(ACT) && pylint app scripts

format:
	@$(ACT) && black app scripts tests -l 120

score:
	@$(ACT) && python scripts/scorecard.py

score-md:
	@$(ACT) && python scripts/scorecard.py --markdown > SCORECARD.md

status:
	@$(ACT) && python -m scripts.status $(if $(WHO),--who $(WHO),)

status-md:
	@$(ACT) && python -m scripts.status --markdown $(if $(WHO),--who $(WHO),)

healthcheck:
	@curl -fsS http://localhost:8080/health && echo

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} \; || true
	find . -type f -name "*.pyc" -delete || true
	rm -rf .pytest_cache .coverage coverage.xml

tree:
	@if command -v tree >/dev/null 2>&1; then \
	    tree -L 3 -I "node_modules|dist|.git|.venv|__pycache__"; \
	else find . -maxdepth 3 -type d -not -path '*/\.*' | sort; fi
