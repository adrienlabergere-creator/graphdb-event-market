# Project Playbook

Single source of truth for the team. If something is not written here or in `docs/`, ask the group before doing it.

- **Pace:** no calendar. The project is a relay: one stage per person, in order. A stage starts when the previous one is merged. `make status` always says where we are.
- **Team:** Adrien, Edgar, Louis, Oscar, Victor
- **Coordination:** every stage owner runs `make status`. Contribution balance is checked with `git shortlog -sn`, and `make score` is run at the end of each stage.
- **Course:** Graph Database and Knowledge, CentraleSupelec. Grading: 100 points, see `SCORECARD.md`.

## 1. Goal

Build the project "Geopolitical Event / Market Correlation Agent" (subject 10, level 3+), scoped to **central-bank and geopolitical events versus rates, FX, commodity and volatility series**.

Hard rules from the subject:

- Neo4j 5.x, Python 3.11+, FastAPI, Docker Compose with at least 3 services, pytest, pylint >= 9.5.
- A LangGraph agent that calls tools, queries Neo4j and exposes the tool calls and graph paths used.
- Temporal correlation is **never** presented as proof of causation. Relations proposed by the agent are hypotheses.
- Educational and analytical use only. No order execution. The README carries the disclaimer.

## 2. Scope

In scope: event and market ingestion, graph model, 5 business endpoints plus `/api/ask`, GDS (projection, 2+ algorithms, one ML workflow), agent with guardrails, Docker stack with reverse proxy, tests, CI, documentation.

Out of scope: web front end, user accounts, real-time streaming, trading signals, extra datasets. Anything else needs an issue and the group's agreement.

## 3. Roles (proposal, swap before the first stage starts)

| Role | Owner | Responsibility | Points |
|---|---|---|---|
| A. Graph and data | Adrien | Schema, constraints, indexes, ingestion, dataset doc, graph diagram, modeling rationale, notebook | 19 |
| B. Analytics, GDS, ML | Oscar | Pathfinding, pattern matching, GDS, ML workflow, optimization, benchmarks | 19 |
| C. Agent and API | Edgar | FastAPI routers and models, LangGraph agent, guardrails, README | 17 |
| D. Infrastructure | Victor | Docker Compose, Dockerfile, reverse proxy, API key, Makefile, architecture diagram, registry image | 17 |
| E. Quality and CI | Louis | Tests, CI workflows, pylint, docstrings, badges, review log | 18 |
| All | everyone | Git: branches, balanced commits, one substantial merged PR each, clean messages | 10 |

Ownership by path is in `.github/CODEOWNERS`. The owner reviews every change to their paths.

## 4. Contracts

- `docs/GRAPH_CONTRACT.md`: node labels, relationship types, properties, constraints, indexes.
- `docs/API_CONTRACT.md`: endpoints, inputs, outputs, status codes, pagination.
- `docs/AGENT_SPEC.md`: agent graph, tools, guardrails, evaluation.

The graph contract is frozen when stage 1 (Adrien) is merged. The API contract and the agent spec are finalized by Edgar at the start of stage 3, then followed. After a freeze, a change needs a PR approved by the owner and the lead. This is what keeps five people consistent.

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

- Code merged to `main` through a reviewed PR, with tests for your own code.
- `make lint` >= 9.5 and `make test` green, new code covered by tests.
- Docstrings on every module, class and function.
- Contracts and README updated if behavior changed.
- The criteria IDs it covers are ticked with evidence in `docs/scorecard_manual.yml` where needed.

## 7. The relay (stages and tracking)

**Where are we?** Run `make status` (or `make status WHO=<Firstname>` for your own next stage with its checklist). The source of truth is `docs/tasks.yml`: every stage has an owner, a checklist, the rubric criteria it covers, its dependency and a status (`todo`, `in_progress`, `in_review`, `done`). Update your own stage **in the PR that delivers it**; a stage is `done` only when its PR is merged.

**Rule of the relay:** one stage per person. You start when the previous stage is `done`; you finish when your PR is merged. After that you do not go back to your stage, except to fix what a reviewer asks. Your remaining job is to review and approve the PRs of the rotation (the reviewer of a stage is the owner of the next one, which is also how they get to know what they build on).

| Stage | Owner | What | Gate (`make score` target) |
|---|---|---|---|
| 1 | Adrien (A) | Graph and data: go/no-go, schema, ingestion, diagrams, notebook | 45 or more |
| 2 | Oscar (B) | Analytics, GDS, ML, benchmarks | 60 or more |
| 3 | Edgar (C) | API contracts, endpoints, LangGraph agent, guardrails | 75 or more |
| 4 | Victor (D) | Docker stack, proxy, Makefile, registry, architecture, screenshots | 85 or more |
| 5 | Louis (E) | Tests, coverage, CI, lint sweep, review log, final scorecard | 90 or more |
| R | All | Defense rehearsal, README contribution table | 90 or more |

Reviews: Oscar reviews Adrien, Edgar reviews Oscar, Victor reviews Edgar, Louis reviews Victor, Adrien reviews Louis. Start reading the previous PR as soon as it is opened: reviewing it is your onboarding.

**Scope policy:** every rubric criterion stays, each piece is kept small and complete (a small data window, 3 to 4 agent tools, one simple ML model, short endpoints, a one-page benchmark). Small and finished beats ambitious and unfinished. Stretch only if everything is green: vector search, more series.

**Data go/no-go** is the first item of stage 1: event and market samples must load into Neo4j. Tell the group as soon as the answer is known, whatever it is.

## 8. Defense preparation

Each person prepares short answers to the questions of their role, and reads all the docs.

- **A:** why this schema, why a node rather than a property (Claim, TradingDay), why each index, how ingestion stays idempotent.
- **B:** how each query works and how its cost grows with the graph, why PageRank/Louvain and not another algorithm, what the ML workflow predicts and how it is evaluated.
- **C:** how the agent is constrained, how an invalid or unsafe generated query is rejected, how verified facts differ from hypotheses.
- **D:** what each container does, ports and data flows, why a reverse proxy, how secrets are handled.
- **E:** what the tests cover, how coverage is measured, what the CI blocks.
- **Everyone:** why correlation is not causation, and why a dense graph structure does not imply a cause.
