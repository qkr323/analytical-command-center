'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Position } from '@/types/portfolio'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts'

const CCY_COLORS: Record<string, string> = {
  USD: '#6366f1', HKD: '#3b82f6', CNH: '#f59e0b', BTC: '#f97316',
  ETH: '#8b5cf6', BNB: '#10b981', SGD: '#ec4899', JPY: '#0ea5e9',
}

function color(ccy: string) {
  return CCY_COLORS[ccy] ?? '#94a3b8'
}

interface CcyRow {
  currency: string
  nativeValue: number
  hkdValue: number
  positions: number
  pct: number
}

function buildBreakdown(positions: Position[]): { cash: CcyRow[]; assets: CcyRow[]; total: CcyRow[] } {
  function rollup(rows: Position[]): CcyRow[] {
    const map: Record<string, { native: number; hkd: number; count: number }> = {}
    for (const p of rows) {
      const c = p.currency
      if (!map[c]) map[c] = { native: 0, hkd: 0, count: 0 }
      map[c].native += parseFloat(p.market_value_local ?? '0')
      map[c].hkd    += parseFloat(p.market_value_hkd  ?? '0')
      map[c].count  += 1
    }
    const totalHkd = Object.values(map).reduce((s, v) => s + v.hkd, 0)
    return Object.entries(map)
      .map(([currency, v]) => ({
        currency,
        nativeValue: v.native,
        hkdValue: v.hkd,
        positions: v.count,
        pct: totalHkd > 0 ? (v.hkd / totalHkd * 100) : 0,
      }))
      .sort((a, b) => b.hkdValue - a.hkdValue)
  }

  const cash   = positions.filter(p => p.asset_type === 'cash')
  const assets = positions.filter(p => p.asset_type !== 'cash')
  return {
    cash:   rollup(cash),
    assets: rollup(assets),
    total:  rollup(positions),
  }
}

function CcyTable({ rows, title }: { rows: CcyRow[]; title: string }) {
  const totalHkd = rows.reduce((s, r) => s + r.hkdValue, 0)
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        <span className="text-xs text-slate-400">
          HK${totalHkd.toLocaleString('en-US', { maximumFractionDigits: 0 })} total
        </span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="text-left px-4 py-2.5 font-medium text-slate-600">Currency</th>
            <th className="text-right px-4 py-2.5 font-medium text-slate-600">Native Value</th>
            <th className="text-right px-4 py-2.5 font-medium text-slate-600">HKD Equiv</th>
            <th className="text-right px-4 py-2.5 font-medium text-slate-600">% of Total</th>
            <th className="text-right px-4 py-2.5 font-medium text-slate-500 text-xs">Positions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 && (
            <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400 text-xs">None</td></tr>
          )}
          {rows.map(r => (
            <tr key={r.currency} className="hover:bg-slate-50">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: color(r.currency) }} />
                  <span className="font-mono font-semibold text-slate-800">{r.currency}</span>
                </div>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600">
                {r.nativeValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                HK${r.hkdValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600">
                <div className="flex items-center justify-end gap-2">
                  <div className="w-20 bg-slate-100 rounded-full h-1.5">
                    <div className="h-1.5 rounded-full" style={{ width: `${r.pct}%`, background: color(r.currency) }} />
                  </div>
                  {r.pct.toFixed(1)}%
                </div>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-500">{r.positions}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function CurrencyPage() {
  const [positions, setPositions] = useState<Position[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)

  useEffect(() => {
    api.getPortfolioSummary()
      .then(d => setPositions(d.positions))
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Loading…</div>
  )
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">{error}</div>
  )

  const { cash, assets, total } = buildBreakdown(positions)

  const pieData = total.map(r => ({ name: r.currency, value: r.hkdValue }))

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-slate-800">Currency Exposure</h1>

      {/* Pie chart + total */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Total Exposure (HKD)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`}>
                {pieData.map(entry => (
                  <Cell key={entry.name} fill={color(entry.name)} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) =>
                `HK$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-1">What this shows</h2>
          <p className="text-xs text-slate-500 leading-relaxed mb-4">
            Currency exposure is the native currency of each position — the currency in which the
            asset is priced and settled. All values are converted to HKD at current FX rates.
          </p>
          <ul className="space-y-2 text-xs text-slate-600">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-medium text-slate-700">Cash exposure</span>
              <span className="text-slate-500">— actual cash balances held in each currency</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-medium text-slate-700">Asset exposure</span>
              <span className="text-slate-500">— investments denominated in each currency (stocks, ETFs, crypto)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-medium text-slate-700">Total exposure</span>
              <span className="text-slate-500">— combined cash + assets, showing your overall FX risk</span>
            </li>
          </ul>
          <p className="mt-4 text-xs text-amber-700 bg-amber-50 rounded-lg p-2.5">
            FX rates update every 30 minutes on Railway. HKD-denominated assets show equal native and HKD values.
          </p>
        </div>
      </div>

      <CcyTable rows={total}  title="Total Currency Exposure (Cash + Assets)" />
      <CcyTable rows={assets} title="Asset Exposure (Investments Only)" />
      <CcyTable rows={cash}   title="Cash Exposure" />
    </div>
  )
}
