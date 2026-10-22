import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { AnswerData, PlanData, TimedEvent, ToolData } from './types'
import type { Status } from './useAgentRun'

const fmtArgs = (args: Record<string, unknown>) =>
  Object.entries(args)
    .filter(([k]) => k !== 'cypher')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`

function Card({ tone = 'slate', title, time, children }: {
  tone?: 'slate' | 'orange' | 'red' | 'green' | 'amber'
  title: string
  time?: number
  children?: React.ReactNode
}) {
  const border = {
    slate: 'border-slate-800',
    orange: 'border-orange-500/40',
    red: 'border-red-500/50',
    green: 'border-emerald-500/40',
    amber: 'border-amber-500/40',
  }[tone]
  const color = {
    slate: 'text-slate-400',
    orange: 'text-orange-300',
    red: 'text-red-300',
    green: 'text-emerald-300',
    amber: 'text-amber-300',
  }[tone]
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`rounded-lg border ${border} bg-slate-900/60 p-3`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-[11px] font-semibold uppercase tracking-wide ${color}`}>{title}</span>
        {time !== undefined && <span className="font-mono text-[10px] text-slate-600">{seconds(time)}</span>}
      </div>
      {children && <div className="mt-1.5 space-y-1.5 text-xs text-slate-300">{children}</div>}
    </motion.div>
  )
}

function Mono({ children }: { children: React.ReactNode }) {
  return (
    <pre className="whitespace-pre-wrap break-words rounded bg-black/40 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-sky-200">
      {children}
    </pre>
  )
}

function PlanCard({ d, t }: { d: PlanData; t: number }) {
  if (d.tool === 'finish')
    return <Card title={`Step ${d.step} · plan`} time={t}>The model has enough results and moves to the answer.</Card>
  return (
    <Card title={`Step ${d.step} · plan`} time={t}>
      <div>
        The model chooses <span className="font-mono text-orange-300">{d.tool}</span>
        {fmtArgs(d.arguments) && <span className="font-mono text-slate-400">({fmtArgs(d.arguments)})</span>}
      </div>
      {typeof d.arguments.cypher === 'string' && <Mono>{d.arguments.cypher}</Mono>}
    </Card>
  )
}

function ToolCard({ d, t }: { d: ToolData; t: number }) {
  if (!d.ok)
    return (
      <Card tone="red" title={`Step ${d.step} · ${d.tool} blocked`} time={t}>
        <div>The guardrail rejected the call before it reached Neo4j:</div>
        <Mono>{d.error}</Mono>
      </Card>
    )
  const touched = d.nodes.reduce<Record<string, number>>((acc, n) => ({ ...acc, [n.label]: (acc[n.label] ?? 0) + 1 }), {})
  return (
    <Card tone="orange" title={`Step ${d.step} · ${d.tool}`} time={t}>
      <div>
        {d.summary} <span className="text-slate-500">· {d.duration_ms} ms in Neo4j</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {Object.entries(touched).map(([label, n]) => (
          <span key={label} className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">
            {n} {label}
          </span>
        ))}
        {d.hops.length > 0 && (
          <span className="rounded bg-orange-500/15 px-1.5 py-0.5 text-[10px] text-orange-300">
            {d.hops.length} edges walked
          </span>
        )}
      </div>
      {d.cypher.map((c, i) => (
        <Mono key={i}>{c}</Mono>
      ))}
    </Card>
  )
}

function AnswerCard({ d, t }: { d: AnswerData; t: number }) {
  const verified = d.status === 'verified'
  return (
    <Card tone={verified ? 'green' : 'amber'} title="Answer" time={t}>
      <p className="text-sm leading-relaxed text-slate-100">{d.answer}</p>
      <div className="flex items-center gap-2">
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${verified ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}
        >
          {d.status}
        </span>
        <div className="h-1.5 flex-1 overflow-hidden rounded bg-slate-800">
          <div className="h-full bg-slate-400" style={{ width: `${d.confidence * 100}%` }} />
        </div>
        <span className="font-mono text-[10px] text-slate-400">confidence {d.confidence.toFixed(2)}</span>
      </div>
      {d.graph_paths.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Graph paths</div>
          {d.graph_paths.slice(0, 5).map((p, i) => (
            <div key={i} className="font-mono text-[11px] text-orange-200">
              {p.join(' → ')}
            </div>
          ))}
        </div>
      )}
      {d.warnings.map((w, i) => (
        <div key={i} className="text-[11px] text-amber-300">
          ⚠ {w}
        </div>
      ))}
      <div className="text-[10px] italic text-slate-500">{d.disclaimer}</div>
    </Card>
  )
}

function Waiting({ label }: { label: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-2 px-1 text-xs text-slate-500"
    >
      <span className="h-1.5 w-1.5 animate-ping rounded-full bg-orange-400" />
      {label}
    </motion.div>
  )
}

export default function StepPanel({ events, status, startedAt, mode }: {
  events: TimedEvent[]
  status: Status
  startedAt: number
  mode: 'live' | 'replay'
}) {
  const bottom = useRef<HTMLDivElement>(null)
  const [now, setNow] = useState(0)

  useEffect(() => {
    if (status !== 'running') return
    const id = setInterval(() => setNow(performance.now()), 100)
    return () => clearInterval(id)
  }, [status])

  // Keep the latest step in view: scroll the side panel itself, never the page.
  useEffect(() => {
    const panel = bottom.current?.closest('aside')
    panel?.scrollTo({ top: panel.scrollHeight, behavior: 'smooth' })
  }, [events.length])

  if (status === 'idle')
    return (
      <p className="text-xs leading-relaxed text-slate-500">
        Pick a question. Each step of the agent appears here as it happens, and the graph shows the nodes it touches.
      </p>
    )

  const last = events[events.length - 1]
  const waitLabel =
    status !== 'running'
      ? null
      : last?.type === 'plan'
        ? 'Running the tool against Neo4j…'
        : last?.type === 'validate'
          ? 'Writing the answer…'
          : 'The model is choosing the next step…'

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-slate-500">
        <span>{mode === 'live' ? 'Live' : 'Replay of a recorded run'}</span>
        {status === 'running' && now > startedAt && <span className="font-mono">{seconds(now - startedAt)}</span>}
      </div>
      <AnimatePresence initial={false}>
        {events.map((e, i) => {
          switch (e.type) {
            case 'parse':
              return e.data.refused ? (
                <Card key={i} tone="red" title="Guardrail · financial advice" time={e.t}>
                  The question asks for advice or an order: refused before any tool is called.
                </Card>
              ) : (
                <Card key={i} title="Guardrail · financial advice" time={e.t}>
                  Passed: the question is analytical.
                </Card>
              )
            case 'plan':
              return <PlanCard key={i} d={e.data} t={e.t} />
            case 'tool':
              return <ToolCard key={i} d={e.data} t={e.t} />
            case 'validate':
              return (
                <Card key={i} title="Validate" time={e.t}>
                  {e.data.warnings.length === 0
                    ? 'Structured output checked, causal-wording filter applied.'
                    : e.data.warnings.map((w, j) => <div key={j}>⚠ {w}</div>)}
                </Card>
              )
            case 'answer':
              return <AnswerCard key={i} d={e.data} t={e.t} />
            case 'error':
              return (
                <Card key={i} tone="red" title="Error" time={e.t}>
                  {e.data.detail}
                </Card>
              )
            default:
              return null
          }
        })}
        {waitLabel && <Waiting key="waiting" label={waitLabel} />}
      </AnimatePresence>
      <div ref={bottom} />
    </div>
  )
}
