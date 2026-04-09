import ProgressBar from './ProgressBar'

interface RequirementGroup {
  name: string
  status: 'SATISFIED' | 'PARTIAL' | 'MISSING'
  percent: number
  satisfied: string[]
  remaining: string[]
  credit_progress: string
}

interface Props {
  group: RequirementGroup
}

const STATUS_COLORS: Record<string, string> = {
  SATISFIED: 'bg-emerald-500',
  PARTIAL: 'bg-amber-500',
  MISSING: 'bg-red-500',
}

const STATUS_LABEL_COLORS: Record<string, string> = {
  SATISFIED: 'var(--accent)',
  PARTIAL: 'var(--accent-amber)',
  MISSING: 'var(--accent-red)',
}

export default function RequirementGroup({ group }: Props) {
  const { name, status, percent, satisfied, remaining, credit_progress } = group
  const barColor = STATUS_COLORS[status] || 'bg-slate-500'
  const labelColor = STATUS_LABEL_COLORS[status] || 'var(--text-subtle)'

  return (
    <div className="glass surface-card rounded-xl p-5 interactive-lift">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h3 className="font-semibold text-sm leading-tight" style={{ color: 'var(--text-primary)' }}>{name}</h3>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="text-xs font-bold uppercase tracking-wide" style={{ color: labelColor }}>
            {status}
          </span>
          <span className="text-xs font-mono" style={{ color: 'var(--text-subtle)' }}>{credit_progress} cr</span>
        </div>
      </div>

      {/* Progress bar */}
      <ProgressBar label="" percent={percent} color={barColor} />

      {/* Satisfied courses */}
      {satisfied.length > 0 && (
        <div className="mt-4">
          <p className="text-xs uppercase tracking-wide font-medium mb-2" style={{ color: 'var(--text-subtle)' }}>
            Satisfied
          </p>
          <div className="flex flex-wrap gap-1.5">
            {satisfied.map((s, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded-full text-xs font-mono"
                style={{
                  background: 'rgba(33, 87, 50, 0.22)',
                  border: '1px solid rgba(76, 217, 130, 0.28)',
                  color: 'var(--accent)',
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Remaining courses */}
      {remaining.length > 0 && (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wide font-medium mb-2" style={{ color: 'var(--text-subtle)' }}>
            Remaining
          </p>
          <div className="flex flex-wrap gap-1.5">
            {remaining.map((r, i) => (
              <span
                key={i}
                className="glass-chip px-2 py-0.5 rounded-full text-xs font-mono"
                style={{ color: 'var(--text-muted)' }}
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
