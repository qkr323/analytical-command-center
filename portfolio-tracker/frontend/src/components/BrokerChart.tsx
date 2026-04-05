'use client'

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const COLORS: Record<string, string> = {
  ibkr:    '#6366f1',
  futu:    '#3b82f6',
  binance: '#f59e0b',
  sofi:    '#10b981',
  osl:     '#8b5cf6',
}

interface Props {
  data: Record<string, string>
}

function fmtM(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

export default function BrokerChart({ data }: Props) {
  const entries = Object.entries(data)
    .map(([k, v]) => ({ broker: k.toUpperCase(), value: parseFloat(v), key: k }))
    .filter(e => e.value > 0)
    .sort((a, b) => b.value - a.value)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-700 mb-4">By Broker (HKD)</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={entries} layout="vertical" margin={{ left: 8, right: 24 }}>
          <XAxis
            type="number"
            tickFormatter={fmtM}
            tick={{ fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="broker"
            tick={{ fontSize: 12, fontWeight: 500 }}
            axisLine={false}
            tickLine={false}
            width={56}
          />
          <Tooltip
            formatter={(v: number) => [`HK${fmtM(v)}`, 'Value']}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {entries.map(e => (
              <Cell key={e.key} fill={COLORS[e.key] ?? '#94a3b8'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
