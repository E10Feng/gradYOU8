interface Props {
  label: string
  percent: number
  color?: string  // e.g. "bg-emerald-500", "bg-red-500" — mapped to fill class
}

export default function ProgressBar({ label, percent, color = "bg-emerald-500" }: Props) {
  const clamped = Math.min(100, Math.max(0, percent))

  const fillClass =
    color === 'bg-amber-500' ? 'progress-fill-warning' :
    color === 'bg-red-500'   ? 'progress-fill-danger' :
    'progress-fill'

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-xs font-mono" style={{ color: 'var(--text-subtle)' }}>{clamped}%</span>
      </div>
      <div className="progress-track h-2">
        <div
          className={`h-full ${fillClass}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
