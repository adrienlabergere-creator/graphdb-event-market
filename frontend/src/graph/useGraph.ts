import { useCallback, useRef, useState } from 'react'
import type { ApiEdge, ApiNode, GLink, GNode, GraphPayload } from '../types'
import { applyTimelineLayout, seedEventPosition } from './layout'

export const linkId = (e: ApiEdge) => `${e.source}|${e.type}|${e.target}`
export const dayIdOf = (event: ApiNode) => `TradingDay:${String(event.props.date ?? '').slice(0, 10)}`

// Holds the drawn graph. Node objects are kept across updates, so the simulation keeps their positions
// and new events slide in instead of the whole graph jumping.
export function useGraph() {
  const nodesById = useRef(new Map<string, GNode>())
  const linksById = useRef(new Map<string, GLink>())
  const [data, setData] = useState<{ nodes: GNode[]; links: GLink[] }>({ nodes: [], links: [] })

  const publish = () => setData({ nodes: [...nodesById.current.values()], links: [...linksById.current.values()] })

  const addEdges = (edges: ApiEdge[]) => {
    for (const e of edges) {
      const id = linkId(e)
      // A link is only drawn when both ends are on screen.
      if (linksById.current.has(id) || !nodesById.current.has(e.source) || !nodesById.current.has(e.target)) continue
      linksById.current.set(id, { id, source: e.source, target: e.target, type: e.type, props: e.props })
    }
  }

  const addNodes = (nodes: ApiNode[]) => {
    const added: GNode[] = []
    for (const n of nodes) {
      if (nodesById.current.has(n.id)) continue
      const node: GNode = { ...n }
      nodesById.current.set(n.id, node)
      added.push(node)
    }
    return added
  }

  const seedEvents = (nodes: GNode[]) => {
    for (const node of nodes) {
      if (node.label === 'Event') seedEventPosition(node, nodesById.current.get(dayIdOf(node)))
    }
  }

  const load = useCallback((payload: GraphPayload) => {
    nodesById.current.clear()
    linksById.current.clear()
    const added = addNodes(payload.nodes)
    applyTimelineLayout(added)
    seedEvents(added)
    addEdges(payload.edges)
    publish()
  }, [])

  // Used from step 4: merge what the agent touched into the drawing.
  const merge = useCallback((nodes: ApiNode[], edges: ApiEdge[]) => {
    const added = addNodes(nodes)
    seedEvents(added)
    addEdges(edges)
    publish()
    return added.map((n) => n.id)
  }, [])

  return { data, load, merge, nodesById }
}
