'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { NavSnapshot } from '@/types/portfolio'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, AreaChart, Area,
} from 'recharts'

const BROKER_COLORS: Record<string, string> = {
  ibkr: '#6366f1', futu: '#3b82f6', binance: '#f59e0b',
  sofi: '#10b981', osl: '#8b5cf6', hangseng: '#ec4899',
}

function fmt(v: number) {
  if (v >= 1_000_000) return `HK$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000)     return `HK$${(v / 1_000).toFixed(0)}K`
  return `HK$${v.toFixed(0)}`
}

function shortDate(d: string) {
  const dt = new Date(d)
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function HistoryPage() {
  const [snapshots, setSnapshots] = useState<NavSnapshot[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [view, setView]           = useState<'total' | 'broker' | 'type'>('total')

  useEffect(() => {
    api.getNavHistory()
      .then(setSnapshots)
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Loading…</div>
  )
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">{error}</div>
  )
  if (snapshots.length === 0) return (
    <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
      <p className="text-slate-500 text-sm">No historical snapshots yet.</p>
      <p className="text-slate-400 text-xs mt-1">Snapshots are created each time you sync positions.</p>
    </div>
  )

  const chartData = snapshots.map(s => {
    const row: Record<string, unknown> = {
      date: shortDate(s.snapshot_date),
      fullDate: s.snapshot_date,
      total: parseFloat(s.total_nav_hkd),
    }
    for (const [k, v] of Object.entries(s.by_broker))    row[`broker_${k}`] = parseFloat(v)
    for (const [k, v] of Object.entries(s.by_asset_type)) row[`type_${k}`]  = parseFloat(v)
    return row
  })

  const allBrokers   = [...new Set(snapshots.flatMap(s => Object.keys(s.by_broker)))]
  const allTypes     = [...new Set(snapshots.flatMap(s => Object.keys(s.by_asset_type)))]

  const first = parseFloat(snapshots[0].total_nav_hkd)
  const last  = parseFloat(snapshots[snapshots.length - 1].total_nav_hkd)
  const change = last - first
  const changePct = first > 0 ? (change / first * 100) : 0

  const TabBtn = ({ v, label }: { v: typeof view; label: string }) => (
    <button
      onClick={() => setView(v)}
      className={`px-3 py-1.5 rounded-md text-sm transition-colors
        ${view === v ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
    >
      {label}
    </button>
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">Portfolio History</h1>
        <span className="text-xs text-slate-400">{snapshots.length} snapshots</span>
      </div>

      {/* Methodology notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-medium mb-1">Portfolio Value History — not adjusted P&L</p>
        <p className="text-xs text-amber-700 leading-relaxed">
          This chart shows your total portfolio market value (NAV) at each snapshot date.
          It does <strong>not</strong> account for deposits, withdrawals, transfers, fees, dividends,
          or FX movements. A rising line means your portfolio grew in HKD value — but not necessarily
          that you made money after accounting for new money added. True P&L (money-weighted return)
          requires transaction-level cash flow data — see the Transactions page to review what is available.
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'First Snapshot', value: fmt(first), sub: snapshots[0].snapshot_date },
          { label: 'Latest Value',   value: fmt(last),  sub: snapshots[snapshots.length - 1].snapshot_date },
          {
            label: 'Total Change',
            value: `${change >= 0 ? '+' : ''}${fmt(change)}`,
            sub: `${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%`,
            positive: change >= 0,
          },
        ].map(({ label, value, sub, positive }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className={`text-lg font-bold tabular-nums
              ${positive === true ? 'text-emerald-600' : positive === false ? 'text-red-600' : 'text-slate-800'}`}>
              {value}
            </p>
            <p className="text-xs text-slate-400">{sub}</p>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700">Portfolio Value (HKD)</h2>
          <div className="flex gap-1">
            <TabBtn v="total"  label="Total"    />
            <TabBtn v="broker" label="By Broker"/>
            <TabBtn v="type"   label="By Type"  />
          </div>
        </div>

        <ResponsiveContainer width="100%" height={360}>
          {view === 'total' ? (
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0}   />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 11 }} width={80} />
              <Tooltip formatter={(v: number) => fmt(v)} labelFormatter={d => `Date: ${d}`} />
              <Area type="monotone" dataKey="total" stroke="#6366f1" fill="url(#navGrad)"
                strokeWidth={2} dot={snapshots.length <= 20} name="Portfolio NAV" />
            </AreaChart>
          ) : view === 'broker' ? (
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 11 }} width={80} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Legend />
              {allBrokers.map(b => (
                <Area key={b} type="monotone" dataKey={`broker_${b}`}
                  stackId="1" stroke={BROKER_COLORS[b] ?? '#94a3b8'}
                  fill={BROKER_COLORS[b] ?? '#94a3b8'} fillOpacity={0.6} name={b.toUpperCase()} />
              ))}
            </AreaChart>
          ) : (
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 11 }} width={80} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Legend />
              {allTypes.map((t, i) => (
                <Line key={t} type="monotone" dataKey={`type_${t}`}
                  stroke={['#6366f1','#3b82f6','#f59e0b','#10b981','#8b5cf6','#ec4899','#f97316'][i % 7]}
                  strokeWidth={2} dot={false} name={t.replace('_', ' ')} />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Snapshot table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">Snapshot History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 font-medium text-slate-600">Date</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Total NAV (HKD)</th>
                {allBrokers.map(b => (
                  <th key={b} className="text-right px-4 py-3 font-medium text-slate-500 text-xs">
                    {b.toUpperCase()}
                  </th>
                ))}
                <th className="text-right px-4 py-3 font-medium text-slate-500 text-xs">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[...snapshots].reverse().map((s, i, arr) => {
                const nav  = parseFloat(s.total_nav_hkd)
                const prev = i < arr.length - 1 ? parseFloat(arr[i + 1].total_nav_hkd) : null
                const diff = prev !== null ? nav - prev : null
                return (
                  <tr key={s.snapshot_date} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-600 tabular-nums text-xs">{s.snapshot_date}</td>
                    <td className="px-4 py-2.5 text-right font-medium tabular-nums">
                      {nav.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0, style: 'currency', currency: 'HKD' })}
                    </td>
                    {allBrokers.map(b => (
                      <td key={b} className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-500">
                        {s.by_broker[b]
                          ? parseFloat(s.by_broker[b]).toLocaleString('en-US', { maximumFractionDigits: 0 })
                          : '—'}
                      </td>
                    ))}
                    <td className={`px-4 py-2.5 text-right tabular-nums text-xs font-medium
                      ${diff === null ? 'text-slate-400' : diff >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {diff === null ? '—' : `${diff >= 0 ? '+' : ''}${fmt(diff)}`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
