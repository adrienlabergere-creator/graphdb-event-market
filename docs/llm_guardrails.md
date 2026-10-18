# LLM guardrails

The agent (`app/agent/`) answers questions by calling tools on the graph. The model only chooses tools and writes the final sentence; every check below is plain code in `app/agent/guardrails.py` (or the flow in `graph.py`), tested without any model in `tests/test_guardrails.py` and `tests/test_agent.py`.

| # | Guardrail | What it blocks | Where |
|---|---|---|---|
| 1 | Read-only allow-list | A query that does not start with `MATCH`, `OPTIONAL MATCH`, `WITH`, `UNWIND` or `RETURN`; `CREATE`, `MERGE`, `SET`, `DELETE`, `DETACH`, `REMOVE`, `DROP`, `LOAD`, `FOREACH`; any `CALL`; several statements. Keywords inside strings and comments are ignored | `check_read_only` |
| 2 | Schema check | Labels, relationship types and properties that are not in `docs/GRAPH_CONTRACT.md` (names are parsed from the contract); a typed one-hop relationship with endpoints or direction that contradicts the frozen contract (mapped in code) | `check_schema`, `check_relationship_endpoints` |
| 3 | Limits | Unbounded traversal (`[*]`, `[*..9]`): the depth must be 6 or less. A `LIMIT` is added when missing (100) and capped (200). Comments are stripped first, so a trailing `// ...` cannot swallow the injected `LIMIT`. Each query has a 10 second timeout and runs in a read-only Neo4j session | `strip_comments`, `check_depth`, `enforce_limit` |
| 4 | Structured output | A malformed model output: the plan and the answer are Pydantic models, retried once, then rejected with a warning. The loop stops after 5 tool calls; a repeated planned call is skipped before it reaches the database | `with_retry`, `MAX_STEPS`, `plan` |
| 5 | Facts versus hypotheses | An answer that presents a correlation as a fact: any answer built on `correlation` or `explain_move` has status `hypothesis`; only answers from `graph_query` can be `verified`. Every answer lists its tool calls, graph paths and Cypher | `ToolResult.hypothesis`, `AgentAnswer` |
| 6 | Causal wording filter | "caused", "because of", "led to", "due to", "resulted in", "triggered"...: the text is rewritten ("was followed by", "in association with") and a warning is added. Applied to every answer, including verified ones, because the graph shows association and never a cause | `find_causal_wording`, `rewrite_causal` |
| 7 | No financial advice or orders | "Should I buy...", "place an order", "dois-je acheter...": refused with an explanation, no tool is called | `is_financial_advice` |

Other protections: tool arguments are validated (unknown series, bad dates become a warning, not a crash); the API answers 503 when Neo4j, the GDS plugin or the model runtime is unreachable.

## Evaluation

Run `python -m scripts.evaluate_agent` after `make schema` and `make ingest`. The evaluator calls the production LangGraph flow and local Ollama model against a read-only session of the loaded Neo4j graph. It saves every question, generated plan and query, final answer, path, warning, duration and metric to [agent_evaluation_results.json](agent_evaluation_results.json). It writes each case as it finishes, so an interrupted run remains inspectable.

The ten fixed questions cover two factual graph queries, two explanations of market moves, three timelines, two correlations and one refused request for financial advice. The expected tool, answer status and path requirement are recorded beside each question in `scripts/evaluate_agent.py`. The first two factual results are checked against direct Neo4j reference queries: Iran has 97 selected events in June 2026; in May the top countries are USA (289), IRN (111), AUS (92), GBR (87) and ISR (61).

The summary uses explicit denominators: answered questions out of ten; expected tool and status among answered questions; neutral wording among answered questions; graph paths among answered cases that require a path; valid model-generated Cypher among all generated Cypher; and rejected unsafe probes among the five fixed probes. A valid Cypher query means it passed the deterministic guardrails, not that the query answered the user's question correctly. This distinction matters: an earlier smoke test used the wrong `OCCURRED_IN` direction and answered “0” for Iran. The final prompt now states the directed schema and DATE syntax, and the guardrail rejects typed relationships whose endpoints or direction contradict the contract. The production example uses a different country and month than the evaluation questions.

The five unsafe probes try a delete, a create, a second statement, an unbounded traversal and an unknown label. They test deterministic rejection only; they are not five sampled model outputs. The [existing screenshot](screenshots/guardrail-rejected.png) shows a separate real model-generated `DELETE` rejected during the stage-four demo. Neither probe set proves that every possible unsafe query is blocked. The agent runs with a Neo4j read-only session as an additional boundary.

### Measured run with `llama3.1:8b`

The saved run answered 10/10 questions. The expected tool appeared in 10/10 answers and the expected `verified` or `hypothesis` status in 10/10. All 10 final answers avoided the causal expressions checked by the filter. All 4 model-generated Cypher queries passed the deterministic validator; all 5 unsafe probes were rejected. Both questions that required a graph path supplied one (2/2). Among the nine questions that used Ollama, the median response time was 140.5 seconds on this local CPU runtime (range 41.2–396.5 seconds). The financial-advice refusal took no model call.

| Question | Observation from the saved answer |
|---|---|
| Iran events in June | Correct count of 97, checked against a direct Neo4j query. |
| Top countries in May | Correct top-five order and the first two counts, checked against Neo4j. |
| Largest Brent and VIX moves | Candidate events were returned as hypotheses, each with five graph paths; GDELT event labels are noisy. |
| VIX in June; EURUSD in March | The model called `timeline` but summarized the period instead of showing the requested daily moves. The EURUSD answer also called a stored closing price an “opening” price. |
| Brent and US10Y correlations | Each answer consisted only of `CAMEO_19`, omitting the coefficient and sample size returned by the tool. |
| WTI, 1–7 May | The answer listed the seven dates, closing prices where available and event counts. Blank weekend prices are retained. |
| Request to buy Brent | Refused before any model or graph tool call. |

Four of the ten answers are therefore clearly incomplete or misleading despite selecting an expected tool and status. In the measured run, the model also planned repeated tool calls. The agent flow now skips an identical planned call before another database query; a [post-fix smoke test](agent_evaluation_postfix_smoke.json) answered 97 for the Iran question, recorded two model plans but executed only one graph query, and added the “Repeated tool call skipped” warning. The saved ten-question run remains the unedited evidence of the model's answer quality before that small flow correction. For complete timelines and correlation values, use the corresponding read-only API endpoints or inspect the tool data rather than relying on the agent's prose.
