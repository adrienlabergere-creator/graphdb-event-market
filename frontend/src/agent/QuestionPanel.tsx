import { useState } from 'react'
import { PRESETS, type Preset } from './presets'
import type { Mode, Status } from './useAgentRun'
import type { ThemeChoice } from '../theme'

interface Props {
  mode: Mode
  setMode: (m: Mode) => void
  status: Status
  available: Set<string> // presets with a recorded trace
  activeId: string | null
  onAsk: (question: string, preset?: Preset) => void
  onStop: () => void
  onDownload: (() => void) | null
  theme: ThemeChoice
  setTheme: (t: ThemeChoice) => void
}

function Section({ children }: { children: string }) {
  return <div className="px-2 pb-1 pt-5 text-[12px] font-medium text-faint">{children}</div>
}

function Segmented<T extends string>({ value, options, onChange, disabled }: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  disabled?: boolean
}) {
  return (
    <div className="grid rounded-lg bg-hover p-0.5 text-[13px]" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          disabled={disabled}
          className={`rounded-md px-2 py-1 transition-colors ${value === o.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// Laid out like Claude's sidebar: a title, then sections of plain rows.
export default function QuestionPanel(props: Props) {
  const { mode, setMode, status, available, activeId, onAsk, onStop, onDownload, theme, setTheme } = props
  const [text, setText] = useState('')
  const running = status === 'running'
  const answers = PRESETS.filter((p) => !p.shows.startsWith('Guardrail'))
  const guardrails = PRESETS.filter((p) => p.shows.startsWith('Guardrail'))

  const row = (p: Preset) => {
    const disabled = running || (mode === 'replay' && !available.has(p.id))
    const active = activeId === p.id
    return (
      <button
        key={p.id}
        disabled={disabled}
        onClick={() => onAsk(p.question, p)}
        className={`block w-full rounded-lg px-2 py-1.5 text-left transition-colors disabled:opacity-40 ${active ? 'bg-hover' : 'hover:bg-hover'} disabled:hover:bg-transparent`}
      >
        <div className="truncate text-[14px] text-ink">{p.question}</div>
        <div className="truncate text-[12px] text-faint">
          {mode === 'replay' && !available.has(p.id) ? 'No recording yet' : p.shows.replace('Guardrail: ', '')}
        </div>
      </button>
    )
  }

  return (
    <div className="flex h-full flex-col px-2 py-3">
      <div className="px-2">
        <div className="font-serif text-[20px] leading-tight text-ink">Event–Market Graph</div>
        <div className="mt-0.5 text-[12px] text-faint">Geopolitical events and market moves · Feb–Jul 2026</div>
      </div>

      <div className="mt-4 px-1">
        <Segmented
          value={mode}
          onChange={setMode}
          disabled={running}
          options={[
            { value: 'live', label: 'Live' },
            { value: 'replay', label: 'Replay' },
          ]}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <Section>Questions</Section>
        {answers.map(row)}
        <Section>Guardrails</Section>
        {guardrails.map(row)}

        {mode === 'live' && (
          <>
            <Section>Ask your own</Section>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (text.trim().length >= 3) onAsk(text.trim())
              }}
              className="space-y-2 px-1"
            >
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (!running && text.trim().length >= 3) onAsk(text.trim())
                  }
                }}
                maxLength={500}
                rows={3}
                placeholder="Which countries had the most events in May?"
                className="w-full resize-none rounded-xl border border-line bg-surface px-3 py-2 text-[14px] text-ink placeholder:text-faint focus:border-accent/60 focus:outline-none"
              />
              <button
                disabled={running || text.trim().length < 3}
                className="w-full rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-accent-ink transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                Ask the agent
              </button>
            </form>
          </>
        )}
      </div>

      <div className="space-y-2 border-t border-line px-1 pt-3">
        {running && (
          <button onClick={onStop} className="w-full rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink hover:bg-hover">
            Stop
          </button>
        )}
        {onDownload && (
          <button onClick={onDownload} className="w-full rounded-lg px-3 py-1.5 text-[13px] text-muted hover:bg-hover hover:text-ink">
            Save this run as a recording
          </button>
        )}
        <Segmented
          value={theme}
          onChange={setTheme}
          options={[
            { value: 'light', label: 'Light' },
            { value: 'dark', label: 'Dark' },
            { value: 'system', label: 'System' },
          ]}
        />
        <p className="px-1 text-[11px] leading-relaxed text-faint">
          Educational use only. No financial advice. A correlation in the graph is never presented as a cause.
        </p>
      </div>
    </div>
  )
}
