import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { forceX, forceY } from 'd3-force'
import type { GLink, GNode } from '../types'
import { COLORS, PALETTES, alwaysLabelled, nodeColor, nodeName, nodeRadius, shortName } from './style'
import type { Resolved } from '../theme'
import { EVENT_BAND_Y } from './layout'
import { dayIdOf } from './useGraph'

// What the agent is doing, as seen by the drawing.
export interface Walk {
  visited: Set<string> // every node touched since the question was asked
  current: Set<string> // nodes touched by the latest tool call
  pastHops: Set<string> // link ids walked during the run
  currentHops: Set<string> // link ids walked by the latest tool call
  focus: string[] | 'all' | null // nodes the camera should frame
}

interface Props {
  data: { nodes: GNode[]; links: GLink[] }
  walk: Walk
  theme: Resolved
}

const endId = (end: string | GNode) => (typeof end === 'string' ? end : end.id)
const MAX_ZOOM = 4

// When a step touches many nodes, only a few get a label, so the names stay readable.
function labelBudget(current: Set<string>, nodes: GNode[]): Set<string> {
  const touched = nodes.filter((n) => current.has(n.id))
  const days = touched.filter((n) => n.label === 'TradingDay').sort((a, b) => a.key.localeCompare(b.key))
  const events = touched.filter((n) => n.label === 'Event')
  const shown = new Set(touched.filter((n) => n.label !== 'TradingDay' && n.label !== 'Event').map((n) => n.id))
  days.forEach((d, i) => {
    if (days.length <= 8 || i % 7 === 0 || i === days.length - 1) shown.add(d.id)
  })
  if (events.length <= 6) events.forEach((e) => shown.add(e.id))
  return shown
}

export default function GraphView({ data, walk, theme }: Props) {
  const palette = PALETTES[theme]
  const box = useRef<HTMLDivElement>(null)
  const fg = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined)
  const firstFit = useRef(true)
  const [size, setSize] = useState({ width: 800, height: 600 })
  const [hover, setHover] = useState<GNode | null>(null)
  const active = walk.visited.size > 0
  const current = walk.current
  const labelled = useMemo(() => labelBudget(current, data.nodes), [current, data.nodes])

  useEffect(() => {
    if (!box.current) return
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }),
    )
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])

  // Pinned rows do the layout. Events are held in a band under the time axis, each one above its own day.
  useEffect(() => {
    const graph = fg.current
    if (!graph) return
    const dayX = new Map(data.nodes.filter((n) => n.label === 'TradingDay').map((n) => [n.id, n.fx ?? 0]))
    // The default centring force would drag free events towards the middle of the pinned rows.
    graph.d3Force('center', null)
    graph.d3Force('charge')?.strength(-10)
    graph.d3Force('link')?.distance(40).strength(0.02)
    graph.d3Force('eventY', forceY<GNode>(EVENT_BAND_Y).strength((n) => (n.label === 'Event' ? 0.2 : 0)))
    graph.d3Force(
      'eventX',
      forceX<GNode>((n) => dayX.get(dayIdOf(n)) ?? 0).strength((n) => (n.label === 'Event' ? 0.3 : 0)),
    )
  }, [data])

  // The camera follows the agent: it frames what the latest step touched, then everything visited.
  useEffect(() => {
    const graph = fg.current
    if (!graph || !walk.focus || walk.focus.length === 0) return
    const ids = walk.focus === 'all' ? null : new Set(walk.focus)
    const fit = setTimeout(() => graph.zoomToFit(900, 70, (n) => ids === null || ids.has(n.id)), 350)
    // A single node would fill the screen: cap the zoom once the fit is done.
    const cap = setTimeout(() => graph.zoom() > MAX_ZOOM && graph.zoom(MAX_ZOOM, 400), 1300)
    return () => {
      clearTimeout(fit)
      clearTimeout(cap)
    }
  }, [walk.focus])

  const linkState = (l: GLink) =>
    walk.currentHops.has(l.id) ? 'current' : walk.pastHops.has(l.id) ? 'past' : 'idle'

  return (
    <div ref={box} className="relative h-full w-full">
      <ForceGraph2D<GNode, GLink>
        ref={fg}
        width={size.width}
        height={size.height}
        graphData={data}
        backgroundColor={palette.background}
        nodeId="id"
        cooldownTicks={150}
        autoPauseRedraw={false}
        onEngineStop={() => {
          if (firstFit.current) fg.current?.zoomToFit(400, 40)
          firstFit.current = false
        }}
        onNodeHover={(n) => setHover(n)}
        linkColor={(l) => {
          const state = linkState(l)
          if (state === 'current') return palette.hot
          if (state === 'past') return palette.hotPast
          if (active) return palette.linkDim
          return l.type === 'PRICE_ON' ? palette.priceLink : palette.link
        }}
        linkWidth={(l) => ({ current: 2.2, past: 1.2, idle: 0.6 })[linkState(l)]}
        linkLineDash={(l) => (l.props.virtual ? [4, 3] : null)}
        linkDirectionalParticles={(l) => (linkState(l) === 'current' ? 3 : 0)}
        linkDirectionalParticleWidth={3.5}
        linkDirectionalParticleSpeed={0.012}
        linkDirectionalParticleColor={() => palette.particle}
        nodeCanvasObject={(node, ctx, scale) => {
          const x = node.x ?? 0
          const y = node.y ?? 0
          const r = nodeRadius(node)
          const visited = walk.visited.has(node.id)
          const current = walk.current.has(node.id)
          // Current nodes pulse.
          if (current) {
            const pulse = (Math.sin(performance.now() / 180) + 1) / 2
            ctx.beginPath()
            ctx.arc(x, y, r + 3 + pulse * 4, 0, 2 * Math.PI)
            ctx.fillStyle = `rgba(${palette.halo},${0.16 + pulse * 0.2})`
            ctx.fill()
          }
          ctx.beginPath()
          ctx.arc(x, y, current ? r * 1.4 : r, 0, 2 * Math.PI)
          ctx.fillStyle = nodeColor(node, palette)
          ctx.globalAlpha = active && !visited ? (node.label === 'Event' ? 0.12 : 0.3) : node.label === 'Event' ? 0.8 : 1
          ctx.fill()
          if (visited) {
            ctx.lineWidth = 1.2 / scale
            ctx.strokeStyle = current ? palette.particle : palette.hot
            ctx.stroke()
          }
          ctx.globalAlpha = 1
          // Full names for what the agent is on (within the label budget) and the hovered node.
          const showFull = node === hover || labelled.has(node.id) || (visited && !current && node.label !== 'Event' && node.label !== 'TradingDay')
          if (alwaysLabelled(node) || showFull) {
            const fontSize = Math.max((current ? 12 : 10) / scale, 2)
            ctx.font = `${current ? 600 : 400} ${fontSize}px Geist, ui-sans-serif, system-ui, -apple-system, sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            ctx.fillStyle = current ? palette.hot : active && !visited ? palette.labelDim : palette.label
            ctx.fillText(showFull ? nodeName(node) : shortName(node), x, y + r + 3 / scale)
          }
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.fillStyle = color
          ctx.beginPath()
          ctx.arc(node.x ?? 0, node.y ?? 0, nodeRadius(node) + 2, 0, 2 * Math.PI)
          ctx.fill()
        }}
      />
      {hover && (
        <div className="pointer-events-none absolute left-3 top-3 max-w-sm rounded-xl border border-line bg-surface/95 px-3 py-2 text-xs shadow-sm">
          <div className="font-medium" style={{ color: COLORS[hover.label] }}>
            {hover.label}
          </div>
          <div className="font-serif text-sm text-ink">{nodeName(hover)}</div>
          <div className="font-mono text-faint">{hover.key}</div>
          <div className="mt-1 text-muted">
            {data.links.filter((l) => endId(l.source) === hover.id || endId(l.target) === hover.id).length} edges on
            screen
          </div>
        </div>
      )}
    </div>
  )
}
