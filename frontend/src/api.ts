import type { GraphPayload } from './types'

export async function fetchGraph(topEvents = 150): Promise<GraphPayload> {
  const res = await fetch(`/api/demo/graph?top_events=${topEvents}`)
  if (!res.ok) throw new Error(`GET /api/demo/graph failed: ${res.status}`)
  return res.json()
}
