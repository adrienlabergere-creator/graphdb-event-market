# API contract (frozen at the start of stage 3)

Owner: role C. Base path `/api`. All responses are JSON validated by Pydantic models. Swagger is served at `/docs`.

After this freeze, a change needs a PR approved by the owner and the lead.

## Common rules

- Pagination on every list endpoint: `limit` (default 20, maximum 100) and `offset` (default 0).
- Errors: `{"detail": "..."}` with 400 (invalid input), 401 (missing or wrong API key, from stage 4), 404 (unknown entity), 422 (validation, raised by FastAPI), 503 (Neo4j, the GDS plugin or the LLM runtime unavailable).
- Every analytical result carries `"status": "hypothesis"` and a `"disclaimer"` field. A correlation is never worded as a cause.
- Sensitive endpoints (`POST`) require the header `X-API-Key`. The key and the Nginx rules are added in stage 4 (role D, criterion SE5); stage 3 ships the endpoints without the check.
- Cypher is always parameterized, carries a `LIMIT` and runs with a bounded traversal depth and a timeout.

## Endpoints

| Method and path | Role | Input | Output |
|---|---|---|---|
| `GET /health`, `GET /health/db` | D | none | status of the API and of the Neo4j connection |
| `GET /api/correlation/event-market` | B | `entity` (theme code or series id), `window` (30 to 365 days, default 90), `limit`, `offset` | list of `{theme, series, corr, n, lag_days, status, disclaimer}` |
| `GET /api/explain/move` | B | `asset` (series id), `window` (30 to 365 days, default 90) | `{asset, move_pct, move_day, candidates: [{event_id, title, score, path}], status, disclaimer}` |
| `GET /api/timeline/{asset}` | B | `from`, `to` (both `YYYY-MM-DD`), `limit`, `offset` | per day: `{day, events, close, ret_1d}` |
| `GET /api/events/{event_id}/paths` | B | `to_series`, `max_depth` (1 to 6, default 4), `limit` | shortest paths: `{nodes, relations, hops}` |
| `GET /api/graph/centrality` | B | `metric` (`pagerank`), `limit` (1 to 100, default 20) | ranked countries: `{iso3, country, score}` (GDS projection) |
| `POST /api/ask` | C | `{"question": "..."}` (3 to 500 characters) | `AgentAnswer` (see `docs/AGENT_SPEC.md`) |

Six routes under `/api`, verified by `make score` (criterion FA1).

Advanced graph queries (rubric: at least 3): correlation, explain/move, event paths, centrality, timeline.
Pathfinding or GDS in at least 2 endpoints: `explain/move`, `events/{id}/paths`, `graph/centrality`.

## Deferred: ingestion endpoints

`POST /api/events/import` and `POST /api/market/sync` were drafted for role A. They are **not implemented**: ingestion
runs through the scripts of stage 1 (`make ingest`, `python -m scripts.ingest_events`, `python -m scripts.ingest_prices`),
which are idempotent and already covered by tests. Exposing them over HTTP would duplicate that path and open the only
write endpoints of the API for no use case in the rubric. If role A wants them, they come with the API key of stage 4
and a PR approved by role A and the lead.
