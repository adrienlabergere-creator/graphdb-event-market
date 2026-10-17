# LLM guardrails

The agent (`app/agent/`) answers questions by calling tools on the graph. The model only chooses tools and writes the final sentence; every check below is plain code in `app/agent/guardrails.py` (or the flow in `graph.py`), tested without any model in `tests/test_guardrails.py` and `tests/test_agent.py`.

| # | Guardrail | What it blocks | Where |
|---|---|---|---|
| 1 | Read-only allow-list | A query that does not start with `MATCH`, `OPTIONAL MATCH`, `WITH`, `UNWIND` or `RETURN`; `CREATE`, `MERGE`, `SET`, `DELETE`, `DETACH`, `REMOVE`, `DROP`, `LOAD`, `FOREACH`; any `CALL`; several statements. Keywords inside strings and comments are ignored | `check_read_only` |
| 2 | Schema check | Labels, relationship types and properties that are not in `docs/GRAPH_CONTRACT.md` (the contract file is parsed, so there is a single source of truth) | `check_schema` |
| 3 | Limits | Unbounded traversal (`[*]`, `[*..9]`): the depth must be 6 or less. A `LIMIT` is added when missing (100) and capped (200). Each query has a 10 second timeout and runs in a read-only Neo4j session | `check_depth`, `enforce_limit`, `graph_query` |
| 4 | Structured output | A malformed model output: the plan and the answer are Pydantic models, retried once, then rejected with a warning. The loop stops after 5 tool calls | `with_retry`, `MAX_STEPS` |
| 5 | Facts versus hypotheses | An answer that presents a correlation as a fact: any answer built on `correlation` or `explain_move` has status `hypothesis`; only answers from `graph_query` can be `verified`. Every answer lists its tool calls, graph paths and Cypher | `ToolResult.hypothesis`, `AgentAnswer` |
| 6 | Causal wording filter | "caused", "because of", "led to", "due to", "resulted in", "triggered"... in a hypothesis: the text is rewritten ("was followed by", "in association with") and a warning is added | `find_causal_wording`, `rewrite_causal` |
| 7 | No financial advice or orders | "Should I buy...", "place an order", "dois-je acheter...": refused with an explanation, no tool is called | `is_financial_advice` |

Other protections: tool arguments are validated (unknown series, bad dates become a warning, not a crash); the API answers 503 when Neo4j, the GDS plugin or the model runtime is unreachable.

## Evaluation

Added in the quality stage: 10 questions with the expected tool and the properties of a good answer, the share of valid queries, the share of unsafe queries rejected, and one rejected unsafe output.
