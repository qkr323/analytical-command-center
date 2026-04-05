'use client'

import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const COLORS: Record<string, string> = {
  cash:             '#94a3b8',
  stock:            '#8b5cf6',
  etf_bond:         '#3b82f6',
  etf_broad_index:  '#6366f1',
  etf_commodity:    '#f59e0b',
  etf_sector:       '#ef4444',
  etf_thematic:     '#f97316',
  crypto:           '#f97316',
  bond_ust:         '#14b8a6',
  bond_ukt:         '#0d9488',
  bond_acgb:        '#0f766e',
  unknown:          '#cbd5e1',
}

const LABELS: Record<string, string> = {
  cash:            'Cash',
  stock:           'Stocks',
  etf_bond:        'Bond ETFs',
  etf_broad_index: 'Index ETFs',
  etf_commodity:   'Commodity ETFs',
  crypto:          'Crypto',
  bond_ust:        'US Treasuries',
  bond_ukt:        'UK Gilts',
  bond_acgb:       'AU Govt Bonds',
}

interface Props {
  data: Record<string, string>
}

function fmt(n: number) {
  if (n >= 1_000_000) return `HK$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `HK$${(n / 1_000).toFixed(0)}K`
  return `HK$${n.toFixed(0)}`
}

export default function AllocationChart({ data }: Props) {
  const entries = Object.entries(data)
    .map(([k, v]) => ({ name: LABELS[k] ?? k, value: parseFloat(v), key: k }))
    .filter(e => e.value > 0)
    .sort((a, b) => b.value - a.value)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-700 mb-4">Asset Allocation</h2>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={entries}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
          >
            {entries.map(e => (
              <Cell key={e.key} fill={COLORS[e.key] ?? '#cbd5e1'} />
            ))}
          </Pie>
          <Tooltip
            formatter={(v: number) => [fmt(v), '']}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend
            formatter={(value) => (
              <span className="text-xs text-slate-600">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
