import { useState } from 'react'
import { PRESETS, type Preset } from './presets'
import type { Mode, Status } from './useAgentRun'

interface Props {
  mode: Mode
  setMode: (m: Mode) => void
  status: Status
  available: Set<string> // presets with a recorded trace
  onAsk: (question: string, preset?: Preset) => void
  onStop: () => void
  onDownload: (() => void) | null
}

export default function QuestionPanel({ mode, setMode, status, available, onAsk, onStop, onDownload }: Props) {
  const [text, setText] = useState('')
  const running = status === 'running'

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-slate-100">Event-Market Graph</h1>
        <p className="mt-1 text-xs text-slate-500">Geopolitical events and market moves in Neo4j, Feb–Jul 2026</p>
      </div>

      <div className="grid grid-cols-2 rounded-md border border-slate-800 p-0.5 text-xs">
        {(['live', 'replay'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            disabled={running}
            className={`rounded px-2 py-1 capitalize ${mode === m ? 'bg-slate-800 text-slate-100' : 'text-slate-500 hover:text-slate-300'}`}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="space-y-1.5">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Questions</div>
        {PRESETS.map((p) => {
          const disabled = running || (mode === 'replay' && !available.has(p.id))
          return (
            <button
              key={p.id}
              disabled={disabled}
              onClick={() => onAsk(p.question, p)}
              className="block w-full rounded-md border border-slate-800 px-3 py-2 text-left hover:border-orange-500/50 hover:bg-slate-900 disabled:opacity-40 disabled:hover:border-slate-800 disabled:hover:bg-transparent"
            >
              <div className="text-xs text-slate-200">{p.question}</div>
              <div className="mt-0.5 text-[10px] text-slate-500">
                {mode === 'replay' && !available.has(p.id) ? 'no recording yet' : p.shows}
              </div>
            </button>
          )
        })}
      </div>

      {mode === 'live' && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (text.trim().length >= 3) onAsk(text.trim())
          }}
          className="space-y-1.5"
        >
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Your own question</div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={500}
            rows={3}
            placeholder="e.g. Which countries had the most events in May?"
            className="w-full resize-none rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:border-orange-500/60 focus:outline-none"
          />
          <button
            disabled={running || text.trim().length < 3}
            className="w-full rounded-md bg-orange-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-orange-400 disabled:opacity-40"
          >
            Ask the agent
          </button>
        </form>
      )}

      <div className="mt-auto space-y-1.5">
        {running && (
          <button onClick={onStop} className="w-full rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300">
            Stop
          </button>
        )}
        {onDownload && (
          <button
            onClick={onDownload}
            className="w-full rounded-md border border-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
          >
            Save this run as a recording
          </button>
        )}
        <p className="text-[10px] leading-relaxed text-slate-600">
          Educational use only. No financial advice. A correlation in the graph is never presented as a cause.
        </p>
      </div>
    </div>
  )
}
