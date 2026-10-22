# Demo UI

A React page that shows the graph and the agent walking through it, step by step.

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

To record a preset: run it in Live, click **Save this run as a recording**, and move the downloaded file to
`public/traces/`. The file is already named after the preset: `vix-june.json`, `brent-themes.json`, `iran-march.json`,
`us10y-fed.json`, `buy-oil.json`, `delete-events.json`.

## Code

| Path | Role |
|---|---|
| `src/App.tsx` | Layout, and how each agent event changes the drawing |
| `src/agent/` | Stream client, presets, live and replay hook, the two side panels |
| `src/graph/` | `react-force-graph-2d` canvas, timeline layout, colours, graph store |
