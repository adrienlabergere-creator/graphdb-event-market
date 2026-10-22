.PHONY: help venv install run docker-build docker-run docker-up docker-stop docker-push ps logs model seed schema test lint format clean tree score score-md status status-md healthcheck ingest stats traces snapshot

PY ?= python3
VENV ?= .venv
ACT = . $(VENV)/bin/activate
# Published API image (GitHub Container Registry). Override: make docker-push VERSION=0.2.0
IMAGE ?= ghcr.io/victorhenz241-eng/graphdb-event-market-api
VERSION ?= 0.1.1
PLATFORMS ?= linux/amd64,linux/arm64

help:
	@echo "Commands:"
	@echo "  make venv          Create local virtualenv ($(VENV))"
	@echo "  make install       Install requirements into $(VENV)"
	@echo "  make run           Run FastAPI (uvicorn) on :8000 with reload"
	@echo "  make docker-build  Build the Docker images"
	@echo "  make docker-run    Start the full Docker Compose stack in the foreground (Ctrl+C stops it)"
	@echo "  make docker-up     Start the full Docker Compose stack in the background"
	@echo "  make docker-stop   Stop the stack (data and model are kept in the volumes)"
	@echo "  make ps            Show the containers and their health"
	@echo "  make logs          Follow the logs (SERVICE=api for one service)"
	@echo "  make model         Download the LLM_MODEL of .env into Ollama (once, about 2 GB)"
	@echo "  make seed          Load schema, prices and events into Neo4j from the api container"
	@echo "  make docker-push   Build the API image for amd64 and arm64 and push it to $(IMAGE)"
	@echo "  make schema        Apply constraints and indexes to Neo4j"
	@echo "  make ingest        Load FRED prices and events into Neo4j (idempotent)"
	@echo "  make stats         Count nodes and relationships by label and type"
	@echo "  make test          Run pytest with coverage"
	@echo "  make lint          Run pylint (score must stay >= 9.5)"
	@echo "  make format        Run black (line length 120)"
	@echo "  make status        Where the project stands (WHO=Firstname for your next task)"
	@echo "  make score         Check the grading checklist automatically"
	@echo "  make traces        Record the demo questions for the demo UI Replay (IDS=\"vix-june ...\" to retry some)"
	@echo "  make snapshot      Save the graph backbone for the public (Vercel) build of the demo UI"
	@echo "  make healthcheck   Call /health and /health/db through the reverse proxy"
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

docker-up:
	docker compose up -d --build

# down without -v: the neo4j_data and ollama_data volumes (graph and model) survive.
docker-stop:
	docker compose down

ps:
	docker compose ps -a

logs:
	docker compose logs -f --tail=100 $(SERVICE)

# Same one-shot service as at start-up, so the model name comes from .env in one place.
model:
	docker compose run --rm ollama-pull

# Idempotent (MERGE): safe to run again. GDELT download takes a few minutes the first time.
seed:
	docker compose exec -T api python -m scripts.apply_schema
	docker compose exec -T api python -m scripts.ingest_prices
	docker compose exec -T api python -m scripts.ingest_events
	docker compose exec -T api python -m scripts.graph_stats

# Needs: docker login ghcr.io (token with write:packages). Multi-arch: Apple Silicon (arm64) and x86 (amd64).
docker-push:
	docker buildx build --platform $(PLATFORMS) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest --push .

schema:
	@$(ACT) && python -m scripts.apply_schema

ingest:
	@$(ACT) && python -m scripts.ingest_prices && python -m scripts.ingest_events

stats:
	@$(ACT) && python -m scripts.graph_stats

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
	@curl -fsS http://localhost:8080/health/db && echo

# Runs on the host with the system python3 (standard library only): the stack must be up.
traces:
	@$(PY) scripts/record_demo_traces.py $(IDS)

# The public build has no backend: it reads this file instead of GET /api/demo/graph.
snapshot:
	@mkdir -p frontend/public/data
	@curl -fsS "http://localhost:8080/api/demo/graph?top_events=150" -o frontend/public/data/graph.json
	@$(PY) -c "import json;d=json.load(open('frontend/public/data/graph.json'));print(len(d['nodes']),'nodes',len(d['edges']),'edges saved in frontend/public/data/graph.json')"

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} \; || true
	find . -type f -name "*.pyc" -delete || true
	rm -rf .pytest_cache .coverage coverage.xml

tree:
	@if command -v tree >/dev/null 2>&1; then \
	    tree -L 3 -I "node_modules|dist|.git|.venv|__pycache__"; \
	else find . -maxdepth 3 -type d -not -path '*/\.*' | sort; fi
