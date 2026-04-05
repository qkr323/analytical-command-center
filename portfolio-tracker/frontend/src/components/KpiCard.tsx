interface KpiCardProps {
  label: string
  value: string
  sub?: string
  positive?: boolean | null   // null = neutral
}

export default function KpiCard({ label, value, sub, positive }: KpiCardProps) {
  const subColor =
    positive === null || positive === undefined
      ? 'text-slate-500'
      : positive
      ? 'text-emerald-600'
      : 'text-red-600'

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-slate-800 tabular-nums">{value}</span>
      {sub && <span className={`text-sm font-medium ${subColor}`}>{sub}</span>}
    </div>
  )
}
