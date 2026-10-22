import { useCallback, useEffect, useRef, useState } from 'react'
import { askStream } from './stream'
import type { AgentEvent, TimedEvent, Trace } from './types'

export type Mode = 'live' | 'replay'
export type Status = 'idle' | 'running' | 'done'

// Replay keeps the order and the rhythm of a recorded run, with long model waits shortened.
const replayDelay = (gap: number, speed: number) => Math.min(Math.max(gap / speed, 350), 1800)

export function useAgentRun(onEvent: (e: AgentEvent) => void) {
  const [events, setEvents] = useState<TimedEvent[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [question, setQuestion] = useState('')
  const [startedAt, setStartedAt] = useState(0)
  const abort = useRef<AbortController | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const onEventRef = useRef(onEvent)
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  const begin = (q: string) => {
    abort.current?.abort()
    abort.current = new AbortController()
    setEvents([])
    setQuestion(q)
    setStatus('running')
    setStartedAt(performance.now())
    return abort.current.signal
  }

  const push = (e: TimedEvent) => {
    setEvents((list) => [...list, e])
    onEventRef.current(e)
    if (e.type === 'done') setStatus('done')
  }

  const runLive = useCallback(async (q: string) => {
    const signal = begin(q)
    const t0 = performance.now()
    const recorded: TimedEvent[] = []
    setTrace(null)
    try {
      await askStream(
        q,
        (e) => {
          const timed = { ...e, t: Math.round(performance.now() - t0) } as TimedEvent
          recorded.push(timed)
          push(timed)
        },
        signal,
      )
    } catch (err) {
      if (signal.aborted) return
      push({ type: 'error', data: { detail: String(err) }, t: Math.round(performance.now() - t0) })
      push({ type: 'done', data: {}, t: Math.round(performance.now() - t0) })
    }
    setTrace({ question: q, recorded_at: new Date().toISOString(), events: recorded })
  }, [])

  const runReplay = useCallback(async (t: Trace, speed = 1) => {
    const signal = begin(t.question)
    setTrace(t)
    let previous = 0
    for (const e of t.events) {
      const wait = e.type === 'start' ? 0 : replayDelay(e.t - previous, speed)
      previous = e.t
      await new Promise((resolve) => setTimeout(resolve, wait))
      if (signal.aborted) return
      push(e)
    }
  }, [])

  const stop = useCallback(() => {
    abort.current?.abort()
    setStatus('done')
  }, [])

  return { events, status, question, startedAt, runLive, runReplay, stop, trace }
}

export async function loadTrace(id: string): Promise<Trace | null> {
  const res = await fetch(`/traces/${id}.json`)
  if (!res.ok) return null
  try {
    return (await res.json()) as Trace
  } catch {
    return null // Vite answers index.html for a missing file
  }
}

export function downloadTrace(trace: Trace, name: string) {
  const blob = new Blob([JSON.stringify(trace, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${name}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}
