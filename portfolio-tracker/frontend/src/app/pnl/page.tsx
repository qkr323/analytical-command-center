'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { PnlSummary, DataQuality } from '@/types/portfolio'
import DataQualityBanner from '@/components/DataQualityBanner'

function hkd(v: string | null | undefined) {
  if (!v) return null
  const n = parseFloat(v)
  if (isNaN(n)) return null
  const sign = n >= 0 ? '+' : ''
  return `${sign}HK$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function hkdAbs(v: string | null | undefined) {
  if (!v) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return `HK$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

const QUALITY_LABELS: Record<string, string> = {
  high: 'Complete', partial: 'Partial', experimental: 'Experimental', unknown: 'Unknown',
}
const QUALITY_COLORS: Record<string, string> = {
  high: 'text-emerald-600', partial: 'text-amber-600', experimental: 'text-orange-600', unknown: 'text-slate-500',
}

export default function PnlPage() {
  const [summary, setSummary]   = useState<PnlSummary | null>(null)
  const [quality, setQuality]   = useState<DataQuality[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [recalcMsg, setRecalc]  = useState<string | null>(null)
  const [recalcLoading, setRecalcLoading] = useState(false)
  const [showQuality, setShowQuality] = useState(false)

  useEffect(() => {
    Promise.all([api.getPnlSummary(), api.getDataQuality()])
      .then(([s, q]) => { setSummary(s); setQuality(q) })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  async function runRecalculate() {
    setRecalcLoading(true)
    setRecalc(null)
    try {
      const res = await api.recalculatePnl()
      setRecalc(`Recalculated ${res.groups_processed} groups. Refreshing…`)
      const [s, q] = await Promise.all([api.getPnlSummary(), api.getDataQuality()])
      setSummary(s)
      setQuality(q)
    } catch (e: unknown) {
      setRecalc(`Error: ${(e as Error).message}`)
    } finally {
      setRecalcLoading(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Loading…</div>
  )
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">{error}</div>
  )
  if (!summary) return null

  const { totals, by_broker } = summary

  const pnlColor = (v: string | null | undefined) => {
    if (!v) return 'text-slate-400'
    return parseFloat(v) >= 0 ? 'text-emerald-600' : 'text-red-600'
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">P&L Analysis</h1>
        <button
          onClick={runRecalculate}
          disabled={recalcLoading}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600
                     hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {recalcLoading ? 'Recalculating…' : 'Recalculate P&L'}
        </button>
      </div>

      {recalcMsg && (
        <p className="text-xs text-slate-500">{recalcMsg}</p>
      )}

      {/* Methodology warning — always visible */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-semibold mb-1">Estimated Trading P&L — not a true investment return</p>
        <p className="text-xs text-amber-700 leading-relaxed">
          Numbers below reflect realized trading gains/losses (average cost method) and current
          unrealized mark-to-market P&L. They do <strong>not</strong> account for deposits,
          withdrawals, transfers, or the timing of capital deployment.
          Dividends and fees are shown where available (IBKR only).
          Sells without sufficient cost basis history are excluded from totals.
        </p>
        {totals.calculation_warnings.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-amber-700">
            {totals.calculation_warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        )}
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Realized Trading P&L', value: totals.realized_trading_pnl_hkd, note: 'completed trades only' },
          { label: 'Unrealized P&L', value: totals.unrealized_pnl_hkd, note: 'mark-to-market' },
          { label: 'Estimated Total Trading P&L', value: totals.estimated_total_trading_pnl_hkd, note: 'realized + unrealized' },
          { label: 'Dividend Income', value: totals.dividend_income_hkd, note: 'IBKR only', noSign: true },
        ].map(({ label, value, note, noSign }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className={`text-lg font-bold tabular-nums ${value ? pnlColor(noSign ? null : value) : 'text-slate-400'}`}>
              {value === null || value === undefined
                ? <span className="text-slate-400 text-sm">No data</span>
                : noSign ? hkdAbs(value) : (hkd(value) ?? '—')}
            </p>
            <p className="text-xs text-slate-400">{note}</p>
          </div>
        ))}
      </div>

      {/* Fees (separate, since it's a cost not income) */}
      {totals.fees_hkd && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
          <div>
            <p className="text-xs text-slate-500">Fees Paid</p>
            <p className="text-sm font-semibold text-red-600 tabular-nums">{hkdAbs(totals.fees_hkd)}</p>
          </div>
          <p className="text-xs text-slate-400">IBKR only · not deducted from P&L totals above</p>
        </div>
      )}

      {/* By broker */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">By Broker</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 font-medium text-slate-600">Broker</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Data Quality</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Realized P&L</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Unrealized P&L</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Est. Total</th>
                <th className="text-right px-4 py-3 font-medium text-slate-500 text-xs">Sells incl/excl</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {by_broker.map(b => (
                <tr key={b.broker} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800 uppercase text-xs">{b.broker}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${QUALITY_COLORS[b.data_quality] ?? 'text-slate-500'}`}>
                      {QUALITY_LABELS[b.data_quality] ?? b.data_quality}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums text-xs font-medium ${pnlColor(b.realized_trading_pnl_hkd)}`}>
                    {b.realized_trading_pnl_hkd !== null ? (hkd(b.realized_trading_pnl_hkd) ?? '—') : '—'}
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums text-xs font-medium ${pnlColor(b.unrealized_pnl_hkd)}`}>
                    {hkd(b.unrealized_pnl_hkd) ?? '—'}
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums text-xs font-medium ${pnlColor(b.estimated_total_trading_pnl_hkd)}`}>
                    {b.estimated_total_trading_pnl_hkd !== null ? (hkd(b.estimated_total_trading_pnl_hkd) ?? '—') : '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-xs text-slate-500">
                    {b.sells_included} / <span className="text-amber-600">{b.sells_excluded}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Data quality detail (collapsible) */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <button
          onClick={() => setShowQuality(v => !v)}
          className="w-full px-5 py-3 flex items-center justify-between text-sm font-semibold text-slate-700
                     hover:bg-slate-50 transition-colors"
        >
          <span>Data Quality Detail</span>
          <span className="text-slate-400 text-xs">{showQuality ? '▲ Hide' : '▼ Show'}</span>
        </button>
        {showQuality && quality.length > 0 && (
          <div className="p-4 border-t border-slate-100">
            <DataQualityBanner items={quality} />
          </div>
        )}
      </div>
    </div>
  )
}
