import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { AnswerData, PlanData, TimedEvent, ToolData } from './types'
import type { Mode, Status } from './useAgentRun'
import { fmtDay, moveText, pathInWords, summarise, type Lookup } from './summary'

const fmtArgs = (args: Record<string, unknown>) =>
  Object.entries(args)
    .filter(([k]) => k !== 'cypher')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`

type Tone = 'plain' | 'accent' | 'bad' | 'ok' | 'warn'

const TONE: Record<Tone, { border: string; title: string }> = {
  plain: { border: 'border-line', title: 'text-faint' },
  accent: { border: 'border-accent/40', title: 'text-accent' },
  bad: { border: 'border-bad/50', title: 'text-bad' },
  ok: { border: 'border-ok/40', title: 'text-ok' },
  warn: { border: 'border-warn/40', title: 'text-warn' },
}

function Card({ tone = 'plain', title, time, children }: { tone?: Tone; title: string; time?: number; children?: ReactNode }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`rounded-xl border ${TONE[tone].border} bg-surface px-3.5 py-3`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-[11px] font-medium tracking-wide ${TONE[tone].title}`}>{title}</span>
        {time !== undefined && <span className="font-mono text-[10px] text-faint">{seconds(time)}</span>}
      </div>
      {children && <div className="mt-1.5 space-y-2 text-[13px] leading-relaxed text-muted">{children}</div>}
    </motion.div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return (
    <pre className="whitespace-pre-wrap break-words rounded-lg bg-code px-2.5 py-2 font-mono text-[11px] leading-relaxed text-ink">
      {children}
    </pre>
  )
}

function Tool({ name }: { name: string }) {
  return <span className="rounded bg-accent-soft px-1 font-mono text-[12px] text-accent">{name}</span>
}

function PlanCard({ d, t }: { d: PlanData; t: number }) {
  if (d.tool === 'finish')
    return (
      <Card title={`Step ${d.step} · Plan`} time={t}>
        The model has enough results and moves on to the answer.
      </Card>
    )
  const args = fmtArgs(d.arguments)
  return (
    <Card title={`Step ${d.step} · Plan`} time={t}>
      <div>
        The model chooses <Tool name={d.tool} />
        {args && <span className="font-mono text-[11px] text-faint"> {args}</span>}
      </div>
      {typeof d.arguments.cypher === 'string' && <Code>{d.arguments.cypher}</Code>}
    </Card>
  )
}

// One line about a tool result. For explain_move it is rebuilt here, so a rate moves in percentage points.
function toolLine(d: ToolData, lookup: Lookup): string {
  const r = d.result as { asset?: string; move_pct?: number; move_day?: string; candidates?: unknown[] } | null
  if (d.tool === 'explain_move' && r?.asset && r.move_pct !== undefined && r.move_day)
    return `Largest move: ${moveText(r.asset, r.move_pct / 100, lookup)} on ${fmtDay(r.move_day)}, ${r.candidates?.length ?? 0} candidate events`
  return d.summary.charAt(0).toUpperCase() + d.summary.slice(1)
}

function ToolCard({ d, t, lookup }: { d: ToolData; t: number; lookup: Lookup }) {
  if (!d.ok)
    return (
      <Card tone="bad" title={`Step ${d.step} · ${d.tool} blocked`} time={t}>
        <div>The guardrail rejected the call before it reached Neo4j:</div>
        <Code>{d.error}</Code>
      </Card>
    )
  const touched = d.nodes.reduce<Record<string, number>>((acc, n) => ({ ...acc, [n.label]: (acc[n.label] ?? 0) + 1 }), {})
  return (
    <Card tone="accent" title={`Step ${d.step} · ${d.tool}`} time={t}>
      <div className="text-ink">
        {toolLine(d, lookup)} <span className="text-faint">· {d.duration_ms} ms in Neo4j</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {Object.entries(touched).map(([label, n]) => (
          <span key={label} className="rounded-md bg-hover px-1.5 py-0.5 text-[11px] text-muted">
            {n} {label}
          </span>
        ))}
        {d.hops.length > 0 && (
          <span className="rounded-md bg-accent-soft px-1.5 py-0.5 text-[11px] text-accent">{d.hops.length} edges walked</span>
        )}
      </div>
      {d.cypher.map((c, i) => (
        <Code key={i}>{c}</Code>
      ))}
    </Card>
  )
}

function AnswerCard({ d, t, events, lookup }: { d: AnswerData; t: number; events: TimedEvent[]; lookup: Lookup }) {
  const [open, setOpen] = useState(false)
  const s = summarise(events, lookup)
  const verified = d.status === 'verified'
  const tone: Tone = s.tone === 'refused' || s.tone === 'blocked' ? 'bad' : verified ? 'ok' : 'warn'
  const showConfidence = s.tone === 'answer'
  return (
    <Card tone={tone} title="In short" time={t}>
      <p className="font-serif text-[17px] leading-snug text-ink">{s.headline}</p>
      {s.lead && <p className="text-ink">{s.lead}</p>}
      {s.items && s.items.length > 0 && (
        <ul className="space-y-1.5">
          {s.items.map((item, i) => (
            <li key={i} className="flex items-baseline justify-between gap-3 border-l-2 border-accent/50 pl-2.5">
              <span className="font-serif text-[14px] text-ink">{item.title}</span>
              <span className="shrink-0 font-mono text-[11px] text-faint">{item.meta}</span>
            </li>
          ))}
        </ul>
      )}
      {s.note && <p>{s.note}</p>}
      {showConfidence && (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${verified ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'}`}
            >
              {d.status}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-hover">
              <div className="h-full rounded-full bg-accent" style={{ width: `${d.confidence * 100}%` }} />
            </div>
            <span className="text-[12px] text-ink tabular-nums">Model's confidence {Math.round(d.confidence * 100)}%</span>
          </div>
          <p className="text-[12px] text-faint">
            {verified
              ? 'A fact read from the graph.'
              : 'How sure the model is that these events go with the move. An association in time, not proof that they caused it.'}
          </p>
        </div>
      )}
      <button onClick={() => setOpen((o) => !o)} className="text-[12px] text-faint underline-offset-2 hover:text-ink hover:underline">
        {open ? 'Hide' : 'Show'} the model's answer and graph paths
      </button>
      {open && (
        <div className="space-y-2 border-t border-line pt-2">
          <p className="italic">“{d.answer}”</p>
          {d.graph_paths.slice(0, 5).map((p, i) => (
            <div key={i} className="text-[12px] text-ink">
              {pathInWords(p, lookup)}
            </div>
          ))}
          {d.warnings.map((w, i) => (
            <div key={i} className="text-[12px] text-warn">
              {w}
            </div>
          ))}
          <p className="text-[11px] text-faint">{d.disclaimer}</p>
        </div>
      )}
    </Card>
  )
}

function Waiting({ label }: { label: string }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2 px-1 text-[13px] text-faint">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
      {label}
    </motion.div>
  )
}

export default function StepPanel({
  events,
  status,
  startedAt,
  mode,
  question,
  lookup,
}: {
  events: TimedEvent[]
  status: Status
  startedAt: number
  mode: Mode
  question: string
  lookup: Lookup
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
      <div className="px-1 pt-2">
        <p className="font-serif text-lg text-ink">How the agent answers</p>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          Pick a question. Each step of the agent appears here as it happens, and the graph lights up the nodes it touches
          and the edges it walks.
        </p>
      </div>
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
    <div className="space-y-2.5">
      <div className="flex items-center justify-between px-1 text-[11px] text-faint">
        <span>{mode === 'live' ? 'Live' : 'Replay of a recorded run'}</span>
        {status === 'running' && now > startedAt && <span className="font-mono">{seconds(now - startedAt)}</span>}
      </div>
      <p className="px-1 font-serif text-[17px] leading-snug text-ink">{question}</p>
      <AnimatePresence initial={false}>
        {events.map((e, i) => {
          switch (e.type) {
            case 'parse':
              return e.data.refused ? (
                <Card key={i} tone="bad" title="Guardrail · financial advice" time={e.t}>
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
              return <ToolCard key={i} d={e.data} t={e.t} lookup={lookup} />
            case 'validate':
              return (
                <Card key={i} title="Validate" time={e.t}>
                  {e.data.warnings.length === 0
                    ? 'Structured output checked, causal-wording filter applied.'
                    : e.data.warnings.map((w, j) => <div key={j}>{w}</div>)}
                </Card>
              )
            case 'answer':
              return <AnswerCard key={i} d={e.data} t={e.t} events={events} lookup={lookup} />
            case 'error':
              return (
                <Card key={i} tone="bad" title="Error" time={e.t}>
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
