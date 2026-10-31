# Event-Market Graph

[![Lint](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/lint.yml/badge.svg)](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/lint.yml)
[![Tests](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/tests.yml/badge.svg)](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/workflows/tests.yml)

> **Disclaimer:** educational and analytical purposes only. This project gives no financial advice and never executes orders. A temporal correlation between an event and a market move is never presented as proof of causation.

## Project description

Subject 10 of the GraphDB projects (level 3+): geopolitical events and market moves in one Neo4j graph.

- Events come from GDELT (tension events by country) and from central-bank rate decisions; prices come from FRED (Brent, WTI, EURUSD, USDJPY, US 10-year yield, VIX).
- Events and prices meet on a shared `TradingDay` node, so the graph can show what happened in the days before a move.
- The API computes correlations, candidate events for a move, shortest paths and PageRank (Graph Data Science).
- A LangGraph agent answers questions in natural language, shows the graph paths and the Cypher it used, and marks every correlation as a hypothesis, never as a cause.
- Window: February to July 2026.

## Installation and execution

Requirements: Docker Desktop or Docker Engine with **Docker Compose v2.24.4 or later** (check with
`docker compose version`; the `!override` tag of `docker-compose.override.example.yml` needs it), `make`, about 12 GB
of free disk space (the Ollama image is 7 GB and the default model about 2 GB).

```bash
cp .env.example .env        # then set NEO4J_PASSWORD and API_KEY (any long random string)
make docker-up              # Neo4j + GDS, Ollama, API and Nginx proxy, in the background
make ps                     # wait for "(healthy)"; ollama-pull shows "Exited (0)" once the model is downloaded
make seed                   # schema, FRED prices and GDELT events into Neo4j (about 5 minutes, idempotent)
make healthcheck            # /health and /health/db through the reverse proxy
```

Swagger is then at http://localhost:8080/docs and the Neo4j Browser at http://localhost:7474. Every port is bound to
127.0.0.1 only. `make docker-stop` stops the stack and keeps the graph and the model in their Docker volumes.

**The model.** On first start, the one-shot `ollama-pull` service downloads `LLM_MODEL` (default `llama3.2:3b`, about
2 GB) into the `ollama_data` volume. The API does not wait for it: until the model is there, `POST /api/ask` answers
503 and every other endpoint works. In Docker, Ollama runs on the CPU: with the default model, 4 GB of Docker memory is
enough (30 to 75 seconds per answer in our test). **With 16 GB of memory or more, use `llama3.1:8b`**: set
`LLM_MODEL=llama3.1:8b` in `.env` (about 5 GB, give Docker Desktop at least 10 GB in Settings, Resources). It follows
the agent's instructions more reliably than the 3b model.

**macOS.** Containers on a Mac cannot use the GPU. To run the model with the native
[Ollama app](https://ollama.com/download) (Metal GPU) instead, run `ollama pull` with the `LLM_MODEL` of your `.env`,
then `cp docker-compose.override.example.yml docker-compose.override.yml` and `make docker-up`: the Ollama containers
are not started and the API calls the app through `host.docker.internal`. On an 8 GB laptop keep the default model:
`llama3.1:8b` does not fit next to Neo4j (one model call took 8 minutes in our test).

**Without Docker for the API** (development): with Neo4j running and `.env` filled, `make install`, then
`make schema`, `make ingest` and `make stats` load the graph from the host, and `make run` serves the API with reload
on http://localhost:8000.

Architecture, ports, data flows and the security choices are explained in [docs/infrastructure.md](docs/infrastructure.md).

## API examples

Swagger is available at `/docs`. List endpoints accept `limit` (default 20, maximum 100) and `offset`. The examples go
through the reverse proxy (port 8080); with `make run` use port 8000.

```bash
# Correlations between event themes and Brent (a theme code or a series id)
curl "http://localhost:8080/api/correlation/event-market?entity=BRENT&window=90&limit=5"

# Largest move of the US 10-year yield and the events that preceded it
curl "http://localhost:8080/api/explain/move?asset=US10Y&window=90"

# Ask the agent: the only endpoint that needs the API key (API_KEY in .env)
curl -X POST http://localhost:8080/api/ask -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" -d '{"question": "Why did the VIX move in June?"}'
```

In Swagger, click **Authorize** and paste the key before trying `POST /api/ask`. The `GET` endpoints are read-only and
public.

Every correlation or explanation carries `"status": "hypothesis"` and a `disclaimer`. The other endpoints are `GET /api/timeline/{asset}`, `GET /api/events/{event_id}/paths` and `GET /api/graph/centrality`.

Error codes: 401 for a missing or wrong API key, 404 for an unknown series, theme or event, 413 for a request body over 16 KB, 422 for an invalid parameter, 429 when the proxy's rate limit is hit (20 requests per second, 10 per minute on `/api/ask`), 503 when Neo4j, the GDS plugin or the model runtime cannot be reached or when the server has no `API_KEY`.

## Demo UI

**Live demo (recorded runs): https://event-market-graph-ten.vercel.app**

A React page (`frontend/`) shows the graph as a timeline (market above, trading days in the middle, events, themes and
countries below) and the agent walking through it: each LangGraph step appears as it happens, the nodes a tool touches
light up and the edges it walks are animated. Each answer opens with a short summary built from the tool results (the
move, its date, the linked events, the model's confidence), worded as an association, never a cause. Light and dark
themes follow the system setting. With the stack running:

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173
```

**Live** streams the agent through `POST /api/demo/ask/stream` (Server-Sent Events, API key added by the dev server from
`.env`); **Replay** plays recorded runs from `frontend/public/traces/` (`make traces`). The public site is a
replay-only build with no backend at all (`make snapshot`, then `npm run build:static`): nothing on it can reach the
API, the model or the database. Details: [frontend/README.md](frontend/README.md).

## Screenshots

Swagger through the reverse proxy: the **Authorize** button and the lock on `POST /api/ask`, the only endpoint that needs the API key.

![Swagger](docs/screenshots/swagger.png)

Neo4j Browser: one `TradingDay` (2026-06-02) where the 6 price series and the 12 most-mentioned events of the day meet, with their countries and themes.

![Neo4j Browser](docs/screenshots/neo4j-browser.png)

An agent answer to "Why did the VIX move in June?": a hypothesis with its confidence, worded as an association, and the tool calls it made.

![Agent answer](docs/screenshots/agent-answer.png)

The same answer continues with the graph paths that support it (event, trading day, series):

```json
"graph_paths": [["GDELT-1307135131", "2026-06-02", "VIX"], ["GDELT-1306987222", "2026-06-02", "VIX"], "..."]
```

A guardrail at work: asked to "Delete all the events", the model wrote `MATCH (e:Event) DELETE e`; the query was rejected before reaching Neo4j (which the API opens read-only anyway), and the graph was untouched.

![Guardrail rejection](docs/screenshots/guardrail-rejected.png)

## Graph schema

![Graph schema](docs/graph_schema.png)

Eight labels: `Event`, `Country`, `Theme`, `Commodity`, `Currency`, `PriceSeries`, `TradingDay`, `Claim`. Events are linked to their country (`OCCURRED_IN`), their category (`HAS_THEME`) and what they mention (`MENTIONS`); prices hang off `(:PriceSeries)-[:PRICE_ON {close, ret_1d}]->(:TradingDay)`. Events and prices meet on `TradingDay`, which is the join between the two worlds. A measured statistic is stored on `(:Theme)-[:CORRELATES_WITH]->(:PriceSeries)` with its window and sample size, and a relation proposed by the ML workflow becomes a `Claim` node with a status and a confidence, never a plain edge. Full contract: [docs/GRAPH_CONTRACT.md](docs/GRAPH_CONTRACT.md).

## System architecture

![System architecture](docs/architecture.png)

Five Docker Compose services: Nginx (the only entry point, `127.0.0.1:8080`, rate limits and timeouts), the FastAPI application with the agent (internal port 8000, API key on `POST /api/ask`), Neo4j with the Graph Data Science plugin, Ollama for the local model (internal only), and a one-shot job that downloads the model. The graph and the model live in two named volumes, `neo4j_data` and `ollama_data`. Source of the diagram: [docs/architecture.dot](docs/architecture.dot) (Graphviz). Details and the reasons behind each choice: [docs/infrastructure.md](docs/infrastructure.md).

## Dataset sources

Two public sources, February to July 2026: **GDELT** for geopolitical events (CAMEO root codes 13 to 19, 30 countries, the 25 most mentioned events per day) and **FRED** for daily prices (Brent, WTI, EURUSD, USDJPY, US 10-year yield, VIX). Central-bank events are derived from the Fed and ECB policy-rate series rather than hand-written. About 4,500 events and 880 price points, rebuilt by anyone with `make ingest`. Sources, filters, licences and exact commands: [docs/DATASETS.md](docs/DATASETS.md).

## Modeling rationale

Why `TradingDay` is a node and not a date property, why a `Claim` is a node rather than a relationship property, why the price sits on the relationship instead of an `Observation` node, which alternatives were rejected and how the model differs from a schema an AI assistant generates from the project description: [docs/modeling_rationale.md](docs/modeling_rationale.md), including the anti-genericity appendix.

## LLM guardrails

The agent only calls four tools (`graph_query`, `correlation`, `timeline`, `explain_move`). Generated Cypher is read-only, checked against the graph contract, bounded in depth and `LIMIT`, and runs with a timeout. Answers are structured, marked `verified` or `hypothesis`, and never worded as a cause. Requests for financial advice are refused. Details: [docs/llm_guardrails.md](docs/llm_guardrails.md).

## Makefile usage

| Command | What it does |
|---|---|
| `make help` | Lists all commands |
| `make install` | Creates `.venv` and installs requirements |
| `make run` | Runs the API locally on port 8000 |
| `make docker-run` | Starts the whole Docker Compose stack in the foreground |
| `make docker-up` | Starts the stack in the background |
| `make docker-stop` | Stops the stack, keeps the data and the model (volumes) |
| `make ps` / `make logs` | Container status and health / logs (`SERVICE=api` for one service) |
| `make model` | Downloads the `LLM_MODEL` of `.env` into Ollama |
| `make seed` | Loads schema, prices and events into Neo4j from the API container |
| `make healthcheck` | Calls `/health` and `/health/db` through the reverse proxy |
| `make docker-push` | Builds the API image for amd64 and arm64 and pushes it to GHCR |
| `make status` | Where the project stands, next task (`WHO=Firstname`) |
| `make test` | Runs pytest with coverage |
| `make lint` | Runs pylint (score at least 9.5) |
| `make traces` | Records the six demo questions for the demo UI Replay (`IDS="brent-march ..."` for some) |
| `make snapshot` | Saves the graph backbone for the public, replay-only build of the demo UI |
| `make clean` | Removes caches |

## Docker image

The API image is public on the GitHub Container Registry, for `linux/amd64` and `linux/arm64`:
[ghcr.io/victorhenz241-eng/graphdb-event-market-api](https://github.com/users/victorhenz241-eng/packages/container/package/graphdb-event-market-api)
(tags `0.1.1` and `latest`).

```bash
docker pull ghcr.io/victorhenz241-eng/graphdb-event-market-api:0.1.1
```

`make docker-up` builds the same image locally from the `Dockerfile`, under the name set by `API_IMAGE` in `.env`
(`event-market-graph-api:dev`), so local builds never overwrite the published tags. It contains only the application
code, the scripts and the graph contract: no `.env`, no data, no key (see `.dockerignore`).

## Team contributions

Filled in at the rehearsal stage from `git shortlog -sn` and the merged pull requests.

| Member | Commits | Share | Pull requests | Role |
|---|---|---|---|---|
| Adrien | | | | |
| Edgar | | | | |
| Louis | | | | |
| Oscar | | | | |
| Victor | | | | |
