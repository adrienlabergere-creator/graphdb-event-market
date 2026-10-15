# Event-Market Graph

[![Lint](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/lint.yml/badge.svg)](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/lint.yml)
[![Tests](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/tests.yml/badge.svg)](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/tests.yml)

> **Disclaimer:** educational and analytical purposes only. This project gives no financial advice and never executes orders. A temporal correlation between an event and a market move is never presented as proof of causation.

## Project description

TODO: what the application does, in five lines. Subject 10 of the GraphDB projects (level 3+).

## Installation and execution

```bash
cp .env.example .env        # then set local values
make docker-run             # Neo4j, local LLM runtime, API, reverse proxy
make help                   # all commands
```

TODO: data loading steps (`make schema`, ingestion commands).

## API examples

TODO: three `curl` examples with real responses. Swagger is available at `/docs`.

## Screenshots

TODO: Swagger, Neo4j Browser graph view, an agent answer with its graph paths (files in `docs/screenshots/`).

## Graph schema

TODO: embed `docs/graph_schema.png` and summarize labels and relationships.

## System architecture

TODO: embed `docs/architecture.png`: services, ports, data flows.

## Dataset sources

TODO: summary and link to `docs/DATASETS.md`.

## Modeling rationale

TODO: summary and link to `docs/modeling_rationale.md`, including the anti-genericity appendix.

## LLM guardrails

TODO: summary and link to `docs/llm_guardrails.md`.

## Makefile usage

| Command | What it does |
|---|---|
| `make help` | Lists all commands |
| `make install` | Creates `.venv` and installs requirements |
| `make run` | Runs the API locally on port 8000 |
| `make docker-run` | Starts the whole Docker Compose stack |
| `make status` | Where the project stands, next task (`WHO=Firstname`) |
| `make test` | Runs pytest with coverage |
| `make lint` | Runs pylint (score at least 9.5) |
| `make clean` | Removes caches |

## Docker image

TODO: link to the image on a public registry.

## Team contributions

TODO: fill in at the end from `git shortlog -sn` and the merged PRs.

| Member | Commits | Share | Pull requests | Role |
|---|---|---|---|---|
| Adrien | | | | |
| Edgar | | | | |
| Louis | | | | |
| Oscar | | | | |
| Victor | | | | |
