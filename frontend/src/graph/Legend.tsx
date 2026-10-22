import { COLORS, LEGEND } from './style'

export default function Legend({ counts }: { counts: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {LEGEND.map((label) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[label] }} />
          {label}
          <span className="text-faint tabular-nums">{counts[label] ?? 0}</span>
        </span>
      ))}
    </div>
  )
}
