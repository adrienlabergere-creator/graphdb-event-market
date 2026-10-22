import { COLORS, LEGEND } from './style'

export default function Legend({ counts }: { counts: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
      {LEGEND.map((label) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLORS[label] }} />
          {label}
          <span className="text-slate-600">{counts[label] ?? 0}</span>
        </span>
      ))}
    </div>
  )
}
