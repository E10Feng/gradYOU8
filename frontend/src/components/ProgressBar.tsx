interface Props {
  label: string
  percent: number
  color?: string  // e.g. "bg-emerald-500", "bg-red-500"
}

export default function ProgressBar({ label, percent, color = "bg-emerald-500" }: Props) {
  const clamped = Math.min(100, Math.max(0, percent))

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <span className="text-sm text-slate-300">{label}</span>
        <span className="text-xs font-mono text-slate-400">{clamped}%</span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
