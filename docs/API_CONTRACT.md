# API contract (draft until the end of phase 0, then frozen)

Owner: role C. Base path `/api`. All responses are JSON validated by Pydantic models. Swagger is served at `/docs`.

## Common rules

- Pagination on every list endpoint: `limit` (default 20, maximum 100) and `offset`.
- Errors: `{"detail": "..."}` with 400 (invalid input), 401 (missing or wrong API key), 404 (unknown entity), 422 (validation), 503 (Neo4j or LLM unavailable).
- Every analytical result carries `"status": "hypothesis"` and a `"disclaimer"` field. A correlation is never worded as a cause.
- Sensitive endpoints (`POST`) require the header `X-API-Key`.
- Cypher is always parameterized, with `LIMIT`, and bounded traversal depth.

## Endpoints

| Method and path | Role | Input | Output |
|---|---|---|---|
| `GET /health`, `GET /health/db` | D | none | status |
| `POST /api/events/import` | A | `start_date`, `end_date`, optional `countries`, `themes`, `limit` | `imported`, `skipped`, `duration_s` |
| `POST /api/market/sync` | A | `series` (list of tickers), `start_date`, `end_date` | `series`, `points` |
| `GET /api/correlation/event-market` | B | `entity` (theme, commodity or currency code), `window` (days) | list of `{theme, series, corr, n, lag_days, status, disclaimer}` |
| `GET /api/explain/move` | B | `asset` (ticker), `window` (days) | `{asset, move_pct, candidates: [{event_id, title, score, path}], status, disclaimer}` |
| `GET /api/timeline/{asset}` | B | `from`, `to` | ordered list of events and price moves |
| `GET /api/events/{event_id}/paths` | B | `to_series`, `max_depth` (default 4, maximum 6) | shortest paths between an event and a series |
| `GET /api/graph/centrality` | B | `metric` (`pagerank`), `limit` | ranked nodes (GDS) |
| `POST /api/ask` | C | `{"question": "..."}` | `AgentAnswer` (see `docs/AGENT_SPEC.md`) |

Advanced graph queries (rubric: at least 3): correlation, explain/move, event paths, centrality, timeline.
Pathfinding or GDS in at least 2 endpoints: `explain/move`, `events/{id}/paths`, `graph/centrality`.
