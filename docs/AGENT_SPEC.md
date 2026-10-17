# Agent specification (frozen at the start of stage 3)

Owner: role C. The agent answers questions such as "Why did the 10-year yield move after the June meeting?" by
traversing the graph, and shows how it got there. Implementation: `app/agent/`. After this freeze, a change needs a PR
approved by the owner and the lead.

The model only does two things: pick the next tool, and write the final sentence. Every check is plain Python code in
`app/agent/guardrails.py`, tested without any model.

## Flow (LangGraph, `app/agent/graph.py`)

```
parse_question -> plan -> run_tools -> plan (loop, 5 steps maximum) -> validate -> answer
```

- `parse_question` refuses a request for financial advice or an order straight away and jumps to `answer`.
- `plan` asks the model for one `Plan` (a tool and its arguments, or `finish`).
- `run_tools` runs the chosen tool, stores the result, the graph paths and the Cypher used.
- After `guardrails.MAX_STEPS` (5) tool calls the loop stops and goes to `validate`.
- `validate` applies the causal-wording filter and decides `verified` versus `hypothesis`.
- `answer` builds the `AgentAnswer`.

State: `question`, `plan`, `tool_calls`, `results`, `paths`, `cypher`, `steps`, `warnings`.

## Tools (`app/agent/tools.py`)

| Tool | Arguments | What it does |
|---|---|---|
| `graph_query` | `{"cypher": "<read-only Cypher>"}` | Runs a validated read-only query. Facts from the graph (counts, lists) |
| `correlation` | `{"series_id": "BRENT", "theme": "CAMEO_19"?, "window": 90}` | Correlation service for a theme and a series |
| `timeline` | `{"series_id": "VIX", "start": "2026-03-01", "end": "2026-03-31"}` | Events and price moves over a period |
| `explain_move` | `{"series_id": "US10Y", "window": 90}` | Largest move and the events that preceded it, with their graph paths |

A tool error (`ValidationError`, `GuardrailError`, `ValueError`) becomes a warning in the answer, never a crash.

## Guardrails (all required, `app/agent/guardrails.py`)

| # | Guardrail | Where |
|---|---|---|
| 1 | Read-only allow-list: a query must start with `MATCH`, `OPTIONAL MATCH`, `WITH`, `UNWIND` or `RETURN`; `CREATE`, `MERGE`, `SET`, `DELETE`, `DETACH`, `REMOVE`, `DROP`, `LOAD`, `FOREACH`, any `CALL` and multiple statements are rejected. Keywords inside strings and comments are ignored | `check_read_only` |
| 2 | Schema check: labels, relationship types and properties must appear in `docs/GRAPH_CONTRACT.md`, which is parsed so there is a single source of truth | `check_schema` |
| 3 | Limits: traversal depth 6 maximum, a `LIMIT` is injected when missing (100) and capped (200), 10 second timeout, read-only Neo4j session | `check_depth`, `enforce_limit`, `graph_query` |
| 4 | Structured output: `Plan` and `AnswerDraft` are Pydantic models, retried once, then rejected with a warning. The loop stops after 5 tool calls | `with_retry`, `MAX_STEPS` |
| 5 | Facts versus hypotheses: an answer built on `correlation` or `explain_move` is always `hypothesis`; only `graph_query` facts can be `verified` | `ToolResult.hypothesis`, `AgentAnswer` |
| 6 | Causal wording filter: "caused", "because of", "led to", "due to", "resulted in", "triggered"... in a hypothesis are rewritten ("was followed by", "in association with") and a warning is added | `find_causal_wording`, `rewrite_causal` |
| 7 | No financial advice or orders: "Should I buy...", "place an order", "dois-je acheter..." are refused with an explanation, no tool is called | `is_financial_advice` |

Constants: `MAX_STEPS = 5`, `MAX_DEPTH = 6`, `DEFAULT_LIMIT = 100`, `MAX_LIMIT = 200`, `QUERY_TIMEOUT_S = 10`.

## Model (`app/agent/llm.py`)

Ollama through `langchain-ollama`, configured by `LLM_MODEL` and `OLLAMA_BASE_URL`. An empty `LLM_MODEL` or an
unreachable runtime raises `LLMUnavailable`, which `POST /api/ask` turns into HTTP 503.

## Output model `AgentAnswer`

`answer`, `status` (`verified` or `hypothesis`), `confidence` (0 to 1), `tool_calls` (`name`, `arguments`,
`duration_ms`), `graph_paths`, `cypher_used`, `warnings`, `disclaimer`.

## Evaluation (criterion GD4)

A file of at least 10 questions with the expected tool and the properties the answer must have (cites a path, is marked
`hypothesis`, contains no causal wording). Report: share of valid generated queries, share of unsafe or invalid queries
correctly rejected, share of answers carrying at least one graph path. Results go in `docs/llm_guardrails.md`.

Per the stage split agreed by the team, this evaluation is delivered in **stage 5 (quality and final deliverables)**;
stage 3 ships the guardrails themselves and their unit tests. The demo must show one successful request and one case
where a guardrail rejects an invalid output.
