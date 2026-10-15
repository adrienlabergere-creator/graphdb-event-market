# Agent specification (draft, finalized by Edgar at the start of stage 3, then frozen)

Owner: role C. The agent answers questions such as "Why did the 10-year yield move after the June meeting?" by traversing the graph, and shows how it got there.

## Flow (LangGraph)

`parse_question` -> `plan` -> `run_tools` (loop, maximum 5 steps) -> `validate` -> `answer`

State: question, plan, list of tool calls with results, collected graph paths, warnings.

## Tools

| Tool | What it does |
|---|---|
| `graph_query` | Runs a read-only Cypher query built from parameterized templates. Free-form generated Cypher is allowed only after validation (below) |
| `correlation` | Calls the correlation service for a theme and a series |
| `timeline` | Returns events and price moves around a date |
| `explain_move` | Returns candidate events and their graph paths for a price move |

## Guardrails (all required)

1. **Read-only Cypher allow-list:** only `MATCH`, `OPTIONAL MATCH`, `WHERE`, `WITH`, `RETURN`, `ORDER BY`, `LIMIT`, `UNWIND`, aggregations. Reject `CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DROP`, `LOAD CSV`, any `CALL` outside an approved list.
2. **Schema check:** labels, relationship types and properties must exist in `docs/GRAPH_CONTRACT.md`.
3. **Limits:** a `LIMIT` is injected if missing, traversal depth is bounded, query time out is set.
4. **Structured output:** the answer is a Pydantic model; a malformed answer is retried once, then rejected.
5. **Facts versus hypotheses:** every statement carries `status` (`verified` or `hypothesis`), the graph paths or sources it relies on, and a confidence. A temporal correlation is always `hypothesis`.
6. **Causal wording filter:** the answer is rejected or rewritten if it states a cause ("caused", "because of", "led to") for a relation that is not `verified`.
7. **No financial advice or orders:** such requests are refused with an explanation.

## Output model `AgentAnswer`

`answer`, `status`, `confidence`, `tool_calls` (name, arguments, duration), `graph_paths`, `cypher_used`, `warnings`, `disclaimer`.

## Evaluation (brief, required by the rubric)

A file of at least 10 questions with the expected tool and the properties the answer must have (cites a path, is marked hypothesis, contains no causal wording). Report: share of valid generated queries, share of unsafe or invalid queries correctly rejected, share of answers with at least one graph path. Results go in `docs/llm_guardrails.md`. The demo must show one successful request and one case where a guardrail rejects an invalid output.
