import ProgressBar from './ProgressBar'

interface CourseDetail {
  code: string
  title: string
  note?: string
  credits?: number
}

interface RequirementGroup {
  name: string
  status: 'SATISFIED' | 'PARTIAL' | 'MISSING'
  percent: number
  satisfied: string[]
  satisfied_details?: CourseDetail[]
  remaining: string[]
  remaining_details?: CourseDetail[]
  credit_progress: string
}

interface Props {
  group: RequirementGroup
}

const STATUS_COLORS: Record<string, string> = {
  SATISFIED: 'progress-fill',
  PARTIAL: 'progress-fill-warning',
  MISSING: 'progress-fill-danger',
}

const STATUS_LABEL_COLORS: Record<string, string> = {
  SATISFIED: 'var(--accent-emerald)',
  PARTIAL: 'var(--accent-amber)',
  MISSING: 'var(--accent-red)',
}

function CoursePill({ code, title, note, variant, credits }: { code: string; title: string; note?: string; variant: 'satisfied' | 'remaining'; credits?: number }) {
  const label = note || code
  const hasTitle = title && title !== code
  const style = variant === 'satisfied'
    ? { background: 'var(--satisfied-bg)', border: '1px solid var(--satisfied-border)', color: 'var(--satisfied-color)' }
    : { color: 'var(--text-muted)' }

  return (
    <span
      className={`${variant === 'remaining' ? 'glass-chip ' : ''}px-2 py-0.5 rounded-full text-xs font-mono`}
      style={style}
      title={hasTitle ? `${label} — ${title} (${credits ?? 3} cr)` : `${label} (${credits ?? 3} cr)`}
    >
      {hasTitle ? `${label} — ${title}` : label}
      {credits != null && (
        <span className="ml-1 opacity-60">({credits} cr)</span>
      )}
    </span>
  )
}

export default function RequirementGroup({ group }: Props) {
  const { name, status, percent, satisfied, satisfied_details, remaining, remaining_details, credit_progress } = group
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
            {satisfied_details ? satisfied_details.map((d, i) => (
              <CoursePill key={i} code={d.code} title={d.title} note={d.note} credits={d.credits} variant="satisfied" />
            )) : satisfied.map((s, i) => (
              <CoursePill key={i} code={s} title="" variant="satisfied" />
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
            {remaining_details ? remaining_details.map((d, i) => (
              <CoursePill key={i} code={d.code} title={d.title} credits={d.credits} variant="remaining" />
            )) : remaining.map((r, i) => (
              <CoursePill key={i} code={r} title="" variant="remaining" />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
