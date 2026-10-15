# Analytics (stage 2)

All services are in `app/services/analytics/`. Each function takes an open Neo4j session first and returns plain lists and dictionaries, so the API and the agent (stage 3) can call them directly.

| Need | Function | Module |
|---|---|---|
| Countries with the most events | `top_countries(session, start, end, limit)` | `queries` |
| Most mentioned events | `top_events(...)` | `queries` |
| Day by day: events, close, return | `timeline(session, series_id, start, end)` | `queries` |
| Events 1 to N days before the largest moves (complex pattern) | `events_before_moves(session, series_id, start, end, max_lag, top_moves, theme)` | `queries` |
| Average absolute move by theme of the day before | `theme_impact(...)` | `queries` |
| Theme vs return correlations, several lags | `compute_theme_correlations(...)`, `store_correlations(...)` | `correlation` |
| Shortest paths | `paths_between_countries(...)`, `paths_event_to_series(...)` | `paths` |
| PageRank and Louvain | `run_gds(session)` | `gds` |
| ML workflow and claims | `run_workflow(...)`, `store_claims(...)` | `link_prediction` |

Run everything on the loaded graph: `python -m scripts.run_analytics --series BRENT --store`.
Measure the queries: `python -m scripts.benchmarks.run_benchmarks --compare-index` (writes `docs/benchmarks.md`).

## Choices to defend

- **Correlation is a statistic, not a cause.** `CORRELATES_WITH` stores `corr`, `n`, `window_days` and `lag_days`. A lag of 1 pairs the return of a day with the events of the day before. Days without events count as 0.
- **`lag_days` on `CORRELATES_WITH`** is an addition to the contract: one relationship per theme, series and lag.
- **The ML workflow never sees the future.** The first 70 percent of the days train the model, the last 30 percent evaluate it (AUC). The threshold of a "large move" (top quartile of absolute returns) is computed on the training period only.
- **Claims are hypotheses.** A `Claim` is written only if the held-out AUC is at least 0.55. Its status is always `hypothesis`, its wording is "associated with", and it is linked to the series and to example events (`ABOUT_SERIES`, `ABOUT_EVENT`).
- **Safe queries.** Values are parameters. The only injected value is the path depth, an integer checked between 1 and 6. Every query has a LIMIT or is bounded by the number of days and themes.
- **Graph Data Science.** The projection (Event, Country, Theme, TradingDay, PriceSeries, undirected) is created, used and dropped by `run_gds`. PageRank and Louvain are reported on countries.
