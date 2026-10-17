# Infrastructure (role D)

How the stack is built and why. Diagram: [architecture.png](architecture.png) (source [architecture.dot](architecture.dot)).

## 1. The containers

| Service | Image | What it does | Port | Data |
|---|---|---|---|---|
| `proxy` | `nginx:1.27-alpine` | Single entry point: forwards to the API, rate limits, timeouts, body size limit | `127.0.0.1:8080` | none |
| `api` | built from `Dockerfile`, published as `ghcr.io/victorhenz241-eng/graphdb-event-market-api` | FastAPI endpoints and the LangGraph agent, with the API key on `POST /api/ask` | 8000, internal only | none (stateless) |
| `neo4j` | `neo4j:5.26` with the GDS plugin | The graph, PageRank and the other GDS algorithms | `127.0.0.1:7474` (Browser), `127.0.0.1:7687` (Bolt) | volume `neo4j_data` |
| `ollama` | `ollama/ollama:0.40.5` | Serves the local model (`llama3.1:8b` by default) | 11434, internal only | volume `ollama_data` |
| `ollama-pull` | `ollama/ollama:0.40.5` | One-shot job: asks `ollama` to download the model, then exits | none | none |

Images are pinned to a version (never `latest`), so the stack a grader starts is the one we tested.

## 2. Ports: what is reachable from where

- Every published port is bound to `127.0.0.1`: only the machine itself can connect. From another computer on the same
  network, ports 8080, 7474, 7687, 11434 and 8000 are closed (checked from the laptop's LAN address).
- The API (8000) and Ollama (11434) are not published at all. Only the containers talk to them, over the internal
  Docker network, by service name (`api`, `ollama`, `neo4j`).
- Neo4j is published so the Neo4j Browser works for the demo and host-side scripts (`make ingest`) can load data.

## 3. Data flows

1. **A request:** client, then `proxy:80` (published as 8080), then `api:8000`. The API reads Neo4j over Bolt with a
   read-only session and parameterized Cypher; for `/api/ask` it also calls Ollama, which returns structured output.
2. **Loading the graph (`make seed`):** the scripts run inside the API container, download GDELT events and FRED
   prices over HTTPS and write them to Neo4j with `MERGE`, so running it twice changes nothing. Downloads are cached in
   `/srv/data`, owned by the non-root user.
3. **The model:** `ollama-pull` asks `ollama` to download it from the Ollama registry into `ollama_data`, once.
4. **The image:** `make docker-push` builds it and pushes it to GHCR; `docker compose` uses it as `API_IMAGE`.

## 4. Why a reverse proxy

- **One entry point.** Clients only know `localhost:8080`; the API and the internal ports stay hidden.
- **Rate limiting** per client IP: 20 requests per second in general, 10 per minute on `/api/ask`, because each agent
  answer costs several model calls. Over the limit, Nginx answers **429** without touching the API.
- **Timeouts:** 120 s in general, 300 s on `/api/ask` (a local model on a CPU is slow).
- **Body size:** requests over 16 KB are refused with **413**; a question is at most 500 characters.
- **Survives a restart of the API:** Nginx resolves `api` through Docker's DNS every 10 seconds, so it follows the
  container when it is recreated with a new IP (tested).

## 5. Why an API key, and only on `POST /api/ask`

- `/api/ask` is the expensive endpoint: each question runs several LLM calls. Without a key anyone who reaches the API
  could keep the CPU busy. The `GET` endpoints are read-only, cheap and paginated, so they stay public.
- The key travels in the `X-API-Key` header and is compared with `API_KEY` from `.env` (`app/security.py`). Swagger shows
  an **Authorize** button because the header is declared as a security scheme.
- Missing or wrong key: **401**. The check runs before any Neo4j session or model call is created.
- **Fail closed:** if the server has no `API_KEY`, the endpoint answers **503** ("API key not configured") instead of
  being open to everyone. A forgotten setting locks the door rather than leaving it open.
- The comparison uses `secrets.compare_digest`, which takes the same time whatever the input, so the key cannot be
  guessed character by character from response times.
- The key protects against abuse of the endpoint. It is not user accounts (out of scope), and on a public server it
  would need HTTPS in front so it does not travel in clear text.

## 6. Secrets

- Real values live only in `.env`, which is in `.gitignore`: it is never committed. `.env.example` lists the variable
  names with placeholder values.
- `.dockerignore` is an allow-list: only `requirements.txt`, `app/`, `scripts/` and `docs/GRAPH_CONTRACT.md` are sent to
  the Docker build. `.env`, `.git`, `.venv` and `data/` can never end up in the published image (checked: no `.env`, no
  key or password in the image, its settings or its build record).
- Docker Compose gives the values to the containers at start (`env_file: .env`, `NEO4J_AUTH`).
- The GHCR login uses a token stored by Docker in the macOS keychain, never in a file of the repository.

## 7. Health checks and start order

- `neo4j`: its HTTP page answers (60 s grace period on first start, while the GDS plugin is downloaded).
- `ollama`: `ollama list` answers.
- `api`: `GET /health` answers 200 (declared in the `Dockerfile`, so it also works outside Compose).
- `depends_on` with `condition: service_healthy`: the API starts only when Neo4j and Ollama are healthy, and the proxy
  only when the API is healthy. Nothing receives traffic before what it depends on is ready.
- The API does **not** wait for `ollama-pull`: the 5 GB download should not block the analytics endpoints. Until the
  model is there, `/api/ask` answers 503 with the reason.
- `make healthcheck` calls `/health` (the API process) and `/health/db` (the API can reach Neo4j) through the proxy.

## 8. Volumes, and why `make docker-stop` keeps them

- `neo4j_data` holds the graph and `ollama_data` the model. A container can be deleted and recreated (new image,
  new settings) without losing them.
- `make docker-stop` runs `docker compose down` **without** `-v`: containers go, volumes stay, so the next start needs
  neither the 5-minute seed nor the 5 GB download. `docker compose down -v` deletes both and is only for a full reset.

## 9. Why a multi-architecture image

Laptops with Apple Silicon run `arm64`, most PCs and servers `amd64`. `make docker-push` builds both with `docker buildx`
and publishes them under one tag; `docker pull` picks the right one automatically. Both variants were checked to start.

## 10. Why a one-shot job pulls the model

- The `ollama` image ships without any model. Someone has to run `ollama pull` once, and `ollama-pull` does it on the
  first `make docker-up`, so a fresh clone needs no manual step.
- It reads `LLM_MODEL` from `.env`, the same variable the API uses, so they cannot disagree. `make model` runs the same
  job again (for example after changing `LLM_MODEL`).
- A second run only checks the files and exits immediately.

## 11. Running it on a Mac, measured

- Docker on a Mac cannot use the GPU: Ollama in a container runs on the CPU and `llama3.1:8b` needs about 6 GB of
  memory, so Docker Desktop needs at least 10 GB.
- `docker-compose.override.example.yml` switches to the native Ollama app (Metal GPU): copy it to
  `docker-compose.override.yml`; the Ollama containers are then not started and the API calls `host.docker.internal`.
- On an 8 GB laptop (Apple M3) `llama3.1:8b` does not fit next to Neo4j: in Docker the model process was killed for
  lack of memory (the API answered a clean 503 in 11 s); with the native app the laptop swapped and one model call took
  8 minutes. With `llama3.2:3b` and the native app, an answer took about 30 seconds.

## 12. How it was tested

From a fresh copy of the repository (no `.env`, no `.venv`, no Docker volumes), with `.env` copied from `.env.example`:

- `make docker-up`: Neo4j (GDS loaded), Ollama, API healthy, proxy up; `ollama-pull` exited 0 after downloading the
  model (about 3 minutes).
- `make seed` from the API container: 4,526 events, 880 prices, 31 countries, in about 5 minutes.
- `make healthcheck`: both checks pass. Correlation, explain-move and centrality (PageRank) answer through the proxy.
- `/api/ask`: 401 without a key or with a wrong key, 413 for a 20 KB body, 429 after a burst of requests.
- The agent through the native app (`llama3.2:3b`): a hypothesis with graph paths in 32 s, a refused request for
  financial advice, a rejected `DELETE` query (graph unchanged).
- Still to check on a machine with 16 GB: a full answer from `llama3.1:8b` inside Docker.
