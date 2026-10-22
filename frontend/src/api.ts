import type { GraphPayload } from './types'
import { STATIC } from './config'

// Live: the backbone from the API. Public build: the same data, saved by `make snapshot`.
export async function fetchGraph(topEvents = 150): Promise<GraphPayload> {
  const url = STATIC ? '/data/graph.json' : `/api/demo/graph?top_events=${topEvents}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Could not load the graph (${url}: ${res.status})`)
  return res.json()
}
