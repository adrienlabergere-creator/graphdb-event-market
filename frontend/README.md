# Demo UI

A React page that shows the graph and the agent walking through it, step by step. Public, replay-only version:
https://event-market-graph-ten.vercel.app

```bash
# with the Docker stack running (make docker-up) and .env filled at the repo root
npm install
npm run dev        # http://localhost:5173
```

The dev server forwards `/api` to `http://localhost:8080` (or `DEMO_API_URL` from `.env`) and adds the `X-API-Key`
header from `API_KEY` in the repo's `.env`, so the key never reaches the browser.

## Live and Replay

- **Live** asks the agent through `POST /api/demo/ask/stream` (Server-Sent Events, one event per LangGraph step).
- **Replay** plays a recorded run from `public/traces/<preset-id>.json`, with long model waits shortened. The steps do
  not need Neo4j or Ollama; the page still loads the backbone graph from the API.

To record the six presets at once, from the repo root with the stack running: `make traces`. Each run is checked
(the refusal is refused, the write query is blocked, the other answers touched the graph) and only good runs are saved
to `public/traces/`. Retry some with `make traces IDS="vix-june iran-march"`. A single live run can also be saved from
the page with **Save this run as a recording**, then moved to `public/traces/`.

## What the page shows

- **Graph:** a timeline layout. Price series above, trading days on the axis, events under their day, then themes and
  countries. The nodes a tool touches pulse, the edges it walks are animated, and the camera follows.
- **Steps:** the guardrail check, each plan (tool, arguments, Cypher), each tool result or rejection, the validation.
- **In short:** a summary built from the tool results rather than the model's sentence, so dates, amounts and event
  names are exact (a rate series moves in percentage points). It speaks of association, never cause.
- **Themes:** light, dark, or the system setting (switch at the bottom of the sidebar).

## Public build (Vercel)

`npm run build:static` makes a version with no backend at all: the graph comes from `public/data/graph.json`
(`make snapshot` from the repo root, stack running) and the agent runs are the recordings in `public/traces/`. Live
mode, the question box and every call to the API are left out of the bundle, so the published page has nothing to
abuse: no API key, no model, no database. `vercel.json` (project root: `frontend`) builds it this way and adds strict
security headers (Content-Security-Policy, no framing, no sniffing, HSTS).

## Code

| Path | Role |
|---|---|
| `src/App.tsx` | Layout, and how each agent event changes the drawing |
| `src/agent/` | Stream client, presets, live and replay hook, the two side panels, the "In short" summary |
| `src/graph/` | `react-force-graph-2d` canvas, timeline layout, colours per theme, graph store |
| `src/theme.ts`, `src/index.css` | Light and dark tokens, theme switch |
| `src/config.ts` | `VITE_STATIC`: the public build without backend |
