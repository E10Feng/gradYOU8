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
  SATISFIED: 'text-emerald-400',
  PARTIAL: 'text-amber-400',
  MISSING: 'text-red-400',
}

export default function RequirementGroup({ group }: Props) {
  const { name, status, percent, satisfied, remaining, credit_progress } = group
  const barColor = STATUS_COLORS[status] || 'bg-slate-500'
  const labelColor = STATUS_LABEL_COLORS[status] || 'text-slate-400'

  return (
    <div className="bg-slate-900 rounded-xl p-5 border border-slate-800">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h3 className="font-semibold text-white text-sm leading-tight">{name}</h3>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className={`text-xs font-bold uppercase tracking-wide ${labelColor}`}>
            {status}
          </span>
          <span className="text-xs text-slate-500 font-mono">{credit_progress} cr</span>
        </div>
      </div>

      {/* Progress bar */}
      <ProgressBar label="" percent={percent} color={barColor} />

      {/* Satisfied courses */}
      {satisfied.length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
            Satisfied
          </p>
          <div className="flex flex-wrap gap-1.5">
            {satisfied.map((s, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-xs font-mono"
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
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
            Remaining
          </p>
          <div className="flex flex-wrap gap-1.5">
            {remaining.map((r, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-xs font-mono border border-slate-700"
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
