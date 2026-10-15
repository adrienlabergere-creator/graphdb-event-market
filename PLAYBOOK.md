# Project Playbook

Single source of truth for the team. If something is not written here or in `docs/`, ask the group before doing it.

- **Pace:** no calendar. The project advances by phases; a phase opens when the gate of the previous one is met. `make status` always says where we are.
- **Team:** Adrien, Edgar, Louis, Oscar, Victor
- **Team lead (to confirm):** Adrien. Coordinates branches and PR reviews, checks contribution balance with `git shortlog -sn`, runs `make score` at the end of each phase.
- **Course:** Graph Database and Knowledge, CentraleSupelec. Grading: 100 points, see `SCORECARD.md`.

## 1. Goal

Build the project "Geopolitical Event / Market Correlation Agent" (subject 10, level 3+), scoped to **central-bank and geopolitical events versus rates, FX and commodity series**.

Hard rules from the subject:

- Neo4j 5.x, Python 3.11+, FastAPI, Docker Compose with at least 3 services, pytest, pylint >= 9.5.
- A LangGraph agent that calls tools, queries Neo4j and exposes the tool calls and graph paths used.
- Temporal correlation is **never** presented as proof of causation. Relations proposed by the agent are hypotheses.
- Educational and analytical use only. No order execution. The README carries the disclaimer.

## 2. Scope

In scope: event and market ingestion, graph model, 5 business endpoints plus `/api/ask`, GDS (projection, 2+ algorithms, one ML workflow), agent with guardrails, Docker stack with reverse proxy, tests, CI, documentation.

Out of scope: web front end, user accounts, real-time streaming, trading signals, extra datasets. Anything else needs an issue and the group's agreement.

## 3. Roles (proposal, swap freely during phase 0)

| Role | Owner | Responsibility | Points |
|---|---|---|---|
| A. Graph and data | Adrien | Schema, constraints, indexes, ingestion, dataset doc, graph diagram, modeling rationale, notebook | 19 |
| B. Analytics, GDS, ML | Victor | Pathfinding, pattern matching, GDS, ML workflow, optimization, benchmarks | 19 |
| C. Agent and API | Edgar | FastAPI routers and models, LangGraph agent, guardrails, README | 17 |
| D. Infrastructure | Louis | Docker Compose, Dockerfile, reverse proxy, API key, Makefile, architecture diagram, registry image | 17 |
| E. Quality and CI | Oscar | Tests, CI workflows, pylint, docstrings, badges, review log | 18 |
| All | everyone | Git: branches, balanced commits, one substantial merged PR each, clean messages | 10 |

Ownership by path is in `.github/CODEOWNERS`. The owner reviews every change to their paths.

## 4. Contracts

- `docs/GRAPH_CONTRACT.md`: node labels, relationship types, properties, constraints, indexes.
- `docs/API_CONTRACT.md`: endpoints, inputs, outputs, status codes, pagination.
- `docs/AGENT_SPEC.md`: agent graph, tools, guardrails, evaluation.

Contracts are frozen **at the end of phase 0**. After that, a change needs a PR approved by the lead and the owner. This is what keeps five people consistent.

## 5. Git workflow

1. `main` is protected: no direct push, PR required, one approval from someone other than the author, CI green.
2. Branches: `feat/<role>-<topic>`, `fix/<role>-<topic>`, `docs/<role>-<topic>`.
3. Commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:` followed by a clear message, one subject line. The only trailer allowed is `Pair: <name>` (for pair work).
4. Pull requests use the template. Link the task ID and the criteria IDs. Keep them focused: one task, one PR.
5. **Merge method: "Merge commit" or "Rebase and merge". Never "Squash"** (it erases individual commits from the contribution statistics).
6. **Review rotation:** B reviews A, C reviews B, D reviews C, E reviews D, A reviews E. For PRs touching a contract, a second reviewer two steps ahead also reviews (A by C, B by D, C by E, D by A, E by B). The reviewer writes at least 2 constructive comments and logs them in `docs/REVIEW_LOG.md`.
7. Secrets: never commit `.env`, keys or tokens (-5 points each). Use `.env.example` for variable names only.
8. Before merging, the author explains the PR in three sentences to the reviewer. Everyone must be able to explain every line they merge.

## 6. Definition of done (every task)

- Code merged to `main` through a reviewed PR.
- `make lint` >= 9.5 and `make test` green, new code covered by tests.
- Docstrings on every module, class and function.
- Contracts and README updated if behavior changed.
- The criteria IDs it covers are ticked with evidence in `docs/scorecard_manual.yml` where needed.

## 7. Phases and tracking

**Where are we?** Run `make status` (or `make status WHO=<Firstname>` for your own next task). The source of truth is `docs/tasks.yml`: every task has an owner, the rubric criteria it covers, its dependencies and a status (`todo`, `in_progress`, `in_review`, `done`). Update your own task **in the PR that delivers it**; a task is `done` only when its PR is merged.

A task is ready when all its dependencies are `done`. If nothing is ready for you, review a teammate's PR (reviews are tasks too: see the rotation in section 5).

Target (MVP): one event window with several hundred events, 3 to 5 market series, 5 business endpoints, PageRank and Louvain, one ML pipeline, an agent answering the 10 evaluation questions with guardrails, Docker stack up, tests at 60 percent or more, all documents. Stretch only once the MVP is green: vector search, more series.

| Phase | Name | Gate to leave it | `make score` at the end |
|---|---|---|---|
| 0 | Foundations | Repo created and protected, kit on `main`, contracts frozen, data go/no-go done, `docker compose up` works from a clean clone | no minimum |
| 1 | Data and API | Ingestion works, 5 business endpoints answer on seed data, tests at 60 percent or more | 45 or more |
| 2 | Analytics and agent | GDS algorithms and ML workflow run, agent answers the evaluation questions with guardrails | 75 or more |
| 3 | Finish and rehearse | All documents done, README complete, clean-clone run OK, team rehearsal done | 90 or more |

**Data go/no-go (task A1):** event and market samples must load into Neo4j. Tell the group as soon as the answer is known, whatever it is.

### Tasks by phase (details and criteria in `docs/tasks.yml`)

| Phase | A. Adrien | B. Victor | C. Edgar | D. Louis | E. Oscar |
|---|---|---|---|---|---|
| 0 | L0 repo, kit, protection. A1 data go/no-go, `schema.cypher` | B1 core Cypher drafts, GDS plugin check | C1 API contract, agent spec, Pydantic stubs | D1 clean-clone `docker compose up`, `.env` | E1 CI check, CODEOWNERS, badges |
| 1 | A2 ingestion scripts | B2 correlation, timeline, shortest-path services | C2 routers, models, errors, `/api/ask` stub | D2 API key, Nginx rules, Makefile, registry image | E2 fixtures and tests, coverage 60 percent |
| 2 | A3 schema diagram, rationale, appendix | B3 GDS, PageRank, Louvain, ML pipeline | C3 LangGraph agent, guardrails, evaluation set | D3 architecture diagram, clean-clone rehearsal | E3 review log, pylint and docstring sweep |
| 3 | A4 notebook, final rationale | B4 benchmarks (EXPLAIN, PROFILE) | C4 final README, `llm_guardrails.md` | D4 final Makefile and clean-clone run | E4 final lint, tests, scorecard |
| 3 | R: everyone rehearses the defense, final `make score`, `git shortlog -sn`, README contribution table | | | | |

## 8. Defense preparation

Each person prepares short answers to the questions of their role, and reads all the docs.

- **A:** why this schema, why a node rather than a property (Claim, TradingDay), why each index, how ingestion stays idempotent.
- **B:** how each query works and how its cost grows with the graph, why PageRank/Louvain and not another algorithm, what the ML workflow predicts and how it is evaluated.
- **C:** how the agent is constrained, how an invalid or unsafe generated query is rejected, how verified facts differ from hypotheses.
- **D:** what each container does, ports and data flows, why a reverse proxy, how secrets are handled.
- **E:** what the tests cover, how coverage is measured, what the CI blocks.
- **Everyone:** why correlation is not causation, and why a dense graph structure does not imply a cause.
