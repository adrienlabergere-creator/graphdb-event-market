import type { ApiNode } from '../types'
import type { TimedEvent, ToolData } from './types'

// A plain-language summary of a run, built from the tool results rather than from the model's sentence:
// the numbers, dates and event names are the graph's, so the summary is exact even when the small model is not.
// It speaks of association in time, never of cause (guardrail 6 of docs/AGENT_SPEC.md).

export type Lookup = (id: string) => ApiNode | undefined

export interface Summary {
  tone: 'answer' | 'refused' | 'blocked' | 'empty'
  headline: string
  lead?: string
  items?: { title: string; meta: string }[]
  note?: string
}

export function fmtDay(day: string): string {
  const d = new Date(`${day.slice(0, 10)}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return day
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
}

// "SOUTH CAROLINA: fight (South Carolina, United States)" -> "Fight · South Carolina, United States"
export function prettyTitle(title: string): string {
  const m = title.match(/^[^:]*:\s*(.+?)\s*\((.+)\)\s*$/)
  if (!m) return title
  const action = m[1].charAt(0).toUpperCase() + m[1].slice(1)
  return `${action} · ${m[2]}`
}

export const seriesName = (id: string, lookup: Lookup) => String(lookup(`PriceSeries:${id}`)?.props.name ?? id)
const isRate = (id: string, lookup: Lookup) => lookup(`PriceSeries:${id}`)?.props.kind === 'rate'

function strength(r: number): string {
  const a = Math.abs(r)
  if (a < 0.1) return 'negligible'
  if (a < 0.3) return 'weak'
  if (a < 0.5) return 'moderate'
  return 'strong'
}

const signed = (r: number) => `${r >= 0 ? '+' : '−'}${Math.abs(r).toFixed(2)}`

export function moveText(series: string, ret: number, lookup: Lookup): string {
  // ret_1d is a simple return, except for rate series where it is a change in percentage points.
  const verb = ret >= 0 ? 'rose' : 'fell'
  const amount = isRate(series, lookup) ? `${Math.abs(ret).toFixed(2)} percentage points` : `${Math.abs(ret * 100).toFixed(1)}%`
  return `${seriesName(series, lookup)} ${verb} ${amount}`
}

function fromExplainMove(t: ToolData, lookup: Lookup): Summary | null {
  const r = t.result as {
    asset: string
    move_pct: number
    move_day: string
    candidates: { event_id: string; title: string; path: string[] }[]
  } | null
  if (!r || !r.candidates) return null
  const items = r.candidates.slice(0, 3).map((c) => {
    const node = lookup(`Event:${c.event_id}`)
    const day = String(node?.props.date ?? c.path[1] ?? '')
    return { title: prettyTitle(c.title), meta: day ? fmtDay(day) : '' }
  })
  return {
    tone: 'answer',
    headline: `${moveText(r.asset, r.move_pct / 100, lookup)} on ${fmtDay(r.move_day)}, its largest daily move in the window.`,
    lead: items.length ? 'In the 3 days before, the graph links it to:' : 'No event in the 3 days before is linked to it.',
    items,
  }
}

function fromCorrelation(t: ToolData, lookup: Lookup): Summary | null {
  const rows = (t.result as { theme: string; series_id: string; lag_days: number; corr: number; n: number }[]) ?? []
  if (!rows.length) return null
  const best = [...rows].sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr))[0]
  const theme = String(lookup(`Theme:${best.theme}`)?.props.label ?? best.theme)
  const when = best.lag_days === 0 ? 'on the same day' : `${best.lag_days} day${best.lag_days > 1 ? 's' : ''} later`
  const others = rows.filter((r) => r !== best && r.theme === best.theme)
  return {
    tone: 'answer',
    headline: `${theme} events (${best.theme}) and ${seriesName(best.series_id, lookup)}: correlation ${signed(best.corr)} ${when}, over ${best.n} days.`,
    lead: `A ${strength(best.corr)} ${best.corr >= 0 ? 'positive' : 'negative'} association.`,
    items: others.map((r) => ({
      title: `${r.lag_days}-day lag`,
      meta: `${signed(r.corr)} · ${strength(r.corr)}`,
    })),
  }
}

function fromTimeline(t: ToolData, lookup: Lookup): Summary | null {
  const rows = ((t.result as { day: string; ret_1d: number | null }[]) ?? []).filter((r) => r.ret_1d !== null)
  const series = String(t.arguments.series_id ?? '').toUpperCase()
  if (!rows.length || !series) return null
  const big = rows.reduce((a, b) => (Math.abs(b.ret_1d!) > Math.abs(a.ret_1d!) ? b : a))
  return {
    tone: 'answer',
    headline: `${moveText(series, big.ret_1d!, lookup)} on ${fmtDay(big.day)}, the largest daily move between ${fmtDay(String(t.arguments.start))} and ${fmtDay(String(t.arguments.end))}.`,
  }
}

function explainBlock(error: string): string {
  const label = error.match(/Unknown label: (\w+)/)
  if (label) return `The model invented a “${label[1]}” node, which does not exist in the graph. The schema check rejected the query.`
  const write = error.match(/Forbidden keyword\(s\): (.+)/)
  if (write) return `The model tried to change the graph (${write[1]}). The agent is read-only, so the query was rejected.`
  return `The guardrail rejected the query: ${error}`
}

export function summarise(events: TimedEvent[], lookup: Lookup): Summary {
  if (events.some((e) => e.type === 'parse' && e.data.refused))
    return {
      tone: 'refused',
      headline: 'Refused before any data was read.',
      note: 'The agent describes events and market moves; it never gives financial advice or places orders.',
    }
  const tools = events.flatMap((e) => (e.type === 'tool' ? [e.data] : []))
  const ok = tools.filter((t) => t.ok)
  const last = (name: string) => [...ok].reverse().find((t) => t.tool === name)
  const built =
    (last('explain_move') && fromExplainMove(last('explain_move')!, lookup)) ||
    (last('correlation') && fromCorrelation(last('correlation')!, lookup)) ||
    (last('timeline') && fromTimeline(last('timeline')!, lookup))
  if (built) return built
  const blocked = tools.find((t) => !t.ok)
  if (blocked)
    return {
      tone: 'blocked',
      headline: 'Blocked before it reached Neo4j: the graph was never touched.',
      note: explainBlock(blocked.error ?? ''),
    }
  const rows = ok.find((t) => t.tool === 'graph_query')
  if (rows && Array.isArray(rows.result) && rows.result.length)
    return { tone: 'answer', headline: `The graph returned ${rows.result.length} row${rows.result.length > 1 ? 's' : ''}.` }
  return { tone: 'empty', headline: 'The agent found no usable data in the graph for this question.' }
}

// A graph path of ids, in words: "Fight · South Carolina → 2 Jun → VIX"
export function pathInWords(path: string[], lookup: Lookup): string {
  return path
    .map((key) => {
      const event = lookup(`Event:${key}`)
      if (event) return prettyTitle(String(event.props.title ?? key))
      if (/^\d{4}-\d{2}-\d{2}/.test(key)) return fmtDay(key)
      return key
    })
    .join(' → ')
}
