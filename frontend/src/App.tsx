import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchGraph } from './api'
import GraphView, { type Walk } from './graph/GraphView'
import Legend from './graph/Legend'
import { linkId, useGraph } from './graph/useGraph'
import QuestionPanel from './agent/QuestionPanel'
import StepPanel from './agent/StepPanel'
import { PRESETS, type Preset } from './agent/presets'
import type { AgentEvent } from './agent/types'
import { downloadTrace, loadTrace, useAgentRun, type Mode } from './agent/useAgentRun'
import { useTheme } from './theme'
import { STATIC } from './config'

const EMPTY_WALK: Walk = { visited: new Set(), current: new Set(), pastHops: new Set(), currentHops: new Set(), focus: null }

export default function App() {
  const { data, load, merge, nodesById } = useGraph()
  const theme = useTheme()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [walk, setWalk] = useState<Walk>(EMPTY_WALK)
  const [mode, setMode] = useState<Mode>(STATIC ? 'replay' : 'live')
  const [available, setAvailable] = useState<Set<string>>(new Set())
  const preset = useRef<Preset | undefined>(undefined)

  useEffect(() => {
    fetchGraph(150).then(load).catch((e: Error) => setError(e.message))
  }, [load])

  // Which presets have a recording in public/traces.
  useEffect(() => {
    Promise.all(PRESETS.map(async (p) => ((await loadTrace(p.id)) ? p.id : null))).then((ids) =>
      setAvailable(new Set(ids.filter((id): id is string => id !== null))),
    )
  }, [])

  // Every agent event, live or replayed, drives the drawing the same way.
  const onEvent = useCallback(
    (e: AgentEvent) => {
      if (e.type === 'start') setWalk({ ...EMPTY_WALK, focus: 'all' })
      if (e.type === 'tool' && e.data.ok) {
        const d = e.data
        merge(d.nodes, [...d.edges, ...d.hops])
        const ids = d.nodes.map((n) => n.id)
        // Each event found also shows where it sits: its day, theme and country light up with it.
        const context = d.edges.flatMap((edge) => [edge.source, edge.target])
        const hopIds = [...d.hops, ...d.edges].map(linkId)
        setWalk((w) => ({
          visited: new Set([...w.visited, ...ids, ...context]),
          current: new Set([...ids, ...context]),
          pastHops: new Set([...w.pastHops, ...hopIds]),
          currentHops: new Set(hopIds),
          focus: ids.length ? ids : w.focus,
        }))
      }
      if (e.type === 'answer') {
        setWalk((w) => ({ ...w, current: new Set(), currentHops: new Set(), focus: w.visited.size ? [...w.visited] : 'all' }))
      }
    },
    [merge],
  )

  const run = useAgentRun(onEvent)

  const ask = async (question: string, p?: Preset) => {
    preset.current = p
    setActiveId(p?.id ?? null)
    if (mode === 'replay' || STATIC) {
      const trace = p ? await loadTrace(p.id) : null
      if (trace) run.runReplay(trace)
      return
    }
    run.runLive(question)
  }

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const n of data.nodes) c[n.label] = (c[n.label] ?? 0) + 1
    return c
  }, [data.nodes])

  const trace = run.trace
  const canDownload = mode === 'live' && run.status === 'done' && trace !== null

  const lookup = (id: string) => nodesById.current.get(id)

  return (
    <div className="grid h-full grid-cols-[288px_1fr_400px] bg-canvas font-sans text-ink">
      <aside className="overflow-hidden border-r border-line bg-sidebar">
        <QuestionPanel
          mode={mode}
          setMode={setMode}
          status={run.status}
          available={available}
          activeId={activeId}
          onAsk={ask}
          onStop={run.stop}
          onDownload={canDownload && trace ? () => downloadTrace(trace, preset.current?.id ?? `run-${Date.now()}`) : null}
          theme={theme.choice}
          setTheme={theme.setChoice}
        />
      </aside>

      <main className="flex min-w-0 flex-col">
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-2.5">
          <Legend counts={counts} />
        </div>
        <div className="min-h-0 flex-1">
          {error ? (
            <p className="p-6 text-sm text-bad">{error}</p>
          ) : (
            <GraphView data={data} walk={walk} theme={theme.resolved} />
          )}
        </div>
      </main>

      <aside className="overflow-y-auto border-l border-line bg-canvas px-4 py-4">
        <StepPanel
          events={run.events}
          status={run.status}
          startedAt={run.startedAt}
          mode={mode}
          question={run.question}
          lookup={lookup}
        />
      </aside>
    </div>
  )
}
