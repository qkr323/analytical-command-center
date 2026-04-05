const STYLES: Record<string, string> = {
  allowed:         'bg-emerald-50 text-emerald-700 border-emerald-200',
  legacy_hold:     'bg-yellow-50  text-yellow-700  border-yellow-200',
  blocked:         'bg-red-50     text-red-700     border-red-200',
  review_required: 'bg-orange-50  text-orange-700  border-orange-200',
}

const LABELS: Record<string, string> = {
  allowed:         'Allowed',
  legacy_hold:     'Legacy Hold',
  blocked:         'Blocked',
  review_required: 'Review',
}

export default function ComplianceBadge({ status }: { status: string }) {
  const key = status.toLowerCase()
  const style = STYLES[key] ?? 'bg-slate-100 text-slate-600 border-slate-200'
  const label = LABELS[key] ?? status

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${style}`}>
      {label}
    </span>
  )
}
