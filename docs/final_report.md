# Event–Market Graph: final technical report

## Purpose and scope

The project relates geopolitical events to market observations in a Neo4j graph. It answers factual questions about the event data and proposes temporal associations between events and price moves. A temporal association is a hypothesis; the project does not infer causality or provide investment advice.

The reproducible observation window is 1 February through 31 July 2026. GDELT supplies machine-coded geopolitical events, and FRED supplies six market series and the rate changes from which central-bank events are derived. The ingestion rules, original source links and reuse conditions are in [DATASETS.md](DATASETS.md).

The team delivered the project as a relay: Adrien owned the graph and data, Oscar the analytics, Edgar the API and agent, Victor the infrastructure, and Louis quality and final evidence. The [task tracker](tasks.yml) records the stage gates and pull requests.

## Reproducible graph

Running `make schema`, `make ingest` and `make stats` against Neo4j 5.26 with the Graph Data Science plugin produced 4,526 `Event` nodes, 880 `PRICE_ON` observations, 202 `TradingDay` nodes, 31 countries, eight themes and six price series. Each event has exactly one country, theme and day. The six series are Brent, WTI, EURUSD, USDJPY, the US 10-year yield and VIX. The source window, daily event cap and idempotent `MERGE` loading are documented in [DATASETS.md](DATASETS.md).

`TradingDay` joins event dates to price dates, including days when markets are closed. Prices and daily returns live on `PRICE_ON` relationships. The model reserves `Claim` nodes for proposed relationships and records their status and evidence separately from observed events. The [graph contract](GRAPH_CONTRACT.md), [schema diagram](graph_schema.png) and [modeling rationale](modeling_rationale.md) specify the labels, relationships and rejected alternatives.

## Analytics and query performance

The service layer exposes parameterized queries for country and event rankings, timelines, candidate events before large moves, theme comparisons, correlations, paths, PageRank and Louvain. The `EVENTS_BEFORE_MOVES` query starts at a price series, selects its largest daily moves, walks to preceding days, then traverses `Event` and `Theme` with a bounded lag. The [analytics guide](analytics.md) covers the service functions and the chronological split used in the NumPy link-prediction workflow. That workflow writes `Claim` nodes only as hypotheses when its held-out AUC clears its threshold.

The [benchmark](benchmarks.md) records `EXPLAIN` and `PROFILE` plans, rows, database hits and five-run median times with and without the `Event.date` index on the loaded graph. For `top_events`, the index reduced database hits from 18,318 to 9,355. For `top_countries`, the indexed plan used 45,263 hits versus 22,767 without it, because this query spans nearly all events and the index is not selective. These measurements support the observed plan choice on this dataset; they do not establish a general speedup.

## API and agent safety

FastAPI exposes six business routes, including `POST /api/ask`. Nginx is the local entry point and rate-limits agent requests to 10 per minute. The agent endpoint requires an API key; health checks and read-only `GET` endpoints do not. Docker Compose contains Neo4j, Ollama, the API, Nginx and a one-time model download job. The [infrastructure guide](infrastructure.md) records ports, startup order, volumes, image publication and a clean-clone test.

The LangGraph agent uses four tools: a bounded read-only Cypher query, correlation, timeline and explanation of a move. Cypher is checked against the graph contract, including known relationship endpoints and directions, then limited before execution in a read-only Neo4j session. The agent marks correlation-based answers as hypotheses, exposes the tool calls, Cypher and graph paths, rewrites causal wording and refuses trading advice. The [guardrail guide](llm_guardrails.md) describes the checks and their limitations.

### Measured agent behavior

Ten fixed questions were run with the local `llama3.1:8b` model against the loaded graph. The expected tool and answer status appeared in all ten results. The four generated Cypher queries passed validation, all five fixed unsafe probes were rejected, and both questions requiring graph paths returned them. The Iran count (97) and May country ranking agreed with direct Neo4j queries. These are safety and routing measures, not a claim of ten accurate answers: two monthly timeline answers omitted the requested daily rows, and two correlation answers omitted their numeric results. One timeline answer also called a closing price an opening price. The full answers, tool calls, warnings and durations are in [agent_evaluation_results.json](agent_evaluation_results.json), with a per-case review in [llm_guardrails.md](llm_guardrails.md).

The nine model-dependent requests had a median latency of 140.5 seconds on the local CPU runtime. The evaluation exposed repeated tool plans; the flow now skips an identical repeat before a second database call. The saved ten-question run predates this flow fix and remains unedited, while a [post-fix smoke result](agent_evaluation_postfix_smoke.json) records one executed query for two identical model plans. The agent is useful for exploring candidate event paths, while the read-only analytical endpoints provide complete numeric tables.

## Quality evidence and reproducibility

The repository has unit, API, Cypher, Neo4j integration and container health tests. The CI workflows run lint and tests, and the README displays their badges. Both [Lint](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/runs/39127898243) and [Tests](https://github.com/adrienlabergere-creator/graphdb-event-market/actions/runs/39127898217) completed successfully on the stage-four merge commit `a804ea4`. Local quality checks use `make lint`, `make test` and `make score`. The detailed [review log](REVIEW_LOG.md) links to actual GitHub comments instead of reconstructing missing reviews.

After the stage-five changes, `make test` passed 135 tests with one container-proxy test skipped because only Neo4j was running; application coverage was 94%. Black found no formatting changes and Pylint scored 10.00/10. The full `make score` self-check returned 93/100 with no detected penalty risk. Its three unclaimed criteria are SE4 (historical review evidence, 1 point), GT3 (balanced commit contributions, 3 points) and GT4 (one substantial merged PR per member, 3 points). The scorecard checks structure and declared evidence; it is not an official grade or a substitute for reviewing the actual answer quality above.

To reproduce the local demo, copy `.env.example` to `.env`, set a password and API key, run `make docker-up`, then `make seed` and `make healthcheck`. Open Swagger at `http://localhost:8080/docs`, call a read-only analytics endpoint, and ask the agent a question with the API key. A response includes a status, confidence, tool calls and, where the tool supplies them, graph paths. The [README](../README.md) gives the commands and example requests.

## Limits and remaining team work

GDELT events are machine coded from news and can contain duplicates or location errors. The event filter retains the 25 most mentioned events per day, so counts describe this selected corpus rather than all world events. FRED prices have non-trading days and the graph is limited to six instruments and six months. Correlations and events preceding moves are descriptive; no causal identification is performed. The local model can produce syntactically valid but irrelevant queries or incomplete prose, so answers need their displayed evidence checked.

The review rule of two constructive comments per pull request is not fully evidenced on PRs #1, #3 and #5. [Louis's stage-five PR #7](https://github.com/adrienlabergere-creator/graphdb-event-market/pull/7) must be reviewed and merged before the rubric's “one substantial merged PR per member” criterion can be claimed. The contribution table and rehearsal belong to the final team stage after that merge. These points remain open in the [scorecard evidence](scorecard_manual.yml) and [task tracker](tasks.yml).
