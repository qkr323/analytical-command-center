'use client'

import { useState } from 'react'
import ComplianceBadge from './ComplianceBadge'
import type { Position } from '@/types/portfolio'

const TYPE_LABELS: Record<string, string> = {
  cash: 'Cash', stock: 'Stock', etf_bond: 'Bond ETF',
  etf_broad_index: 'Index ETF', etf_commodity: 'Commodity ETF',
  crypto: 'Crypto', bond_ust: 'US Treasury', bond_ukt: 'UK Gilt',
  bond_acgb: 'AU Govt Bond', etf_sector: 'Sector ETF',
  etf_thematic: 'Thematic ETF', unknown: '?',
}

function hkd(v: string | null) {
  if (!v) return '—'
  const n = parseFloat(v)
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(1)}K`
  return `$${n.toFixed(0)}`
}

function pnl(v: string | null, pct: string | null) {
  if (!v) return { text: '—', positive: null }
  const n = parseFloat(v)
  const p = pct ? parseFloat(pct).toFixed(2) : null
  const text = `${n >= 0 ? '+' : ''}${hkd(v)}${p ? ` (${n >= 0 ? '+' : ''}${p}%)` : ''}`
  return { text, positive: n >= 0 }
}

interface Props {
  positions: Position[]
  limit?: number
}

type SortKey = 'market_value_hkd' | 'symbol' | 'unrealized_pnl_hkd'

export default function PositionTable({ positions, limit }: Props) {
  const [sort, setSort] = useState<SortKey>('market_value_hkd')
  const [dir, setDir]   = useState<'asc' | 'desc'>('desc')

  function toggle(key: SortKey) {
    if (sort === key) setDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSort(key); setDir('desc') }
  }

  const sorted = [...positions].sort((a, b) => {
    const va = parseFloat(a[sort] ?? '0')
    const vb = parseFloat(b[sort] ?? '0')
    return dir === 'asc' ? va - vb : vb - va
  })

  const rows = limit ? sorted.slice(0, limit) : sorted

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button
      onClick={() => toggle(k)}
      className="flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors"
    >
      {label}
      {sort === k && <span>{dir === 'desc' ? '↓' : '↑'}</span>}
    </button>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200">
            <th className="text-left py-2 pr-4 font-medium">
              <SortBtn k="symbol" label="Symbol" />
            </th>
            <th className="text-left py-2 pr-4 font-medium text-slate-500">Type</th>
            <th className="text-left py-2 pr-4 font-medium text-slate-500">Broker</th>
            <th className="text-right py-2 pr-4 font-medium">
              <SortBtn k="market_value_hkd" label="Value (HKD)" />
            </th>
            <th className="text-right py-2 pr-4 font-medium text-slate-500">Qty</th>
            <th className="text-right py-2 pr-4 font-medium text-slate-500">Price</th>
            <th className="text-right py-2 font-medium">
              <SortBtn k="unrealized_pnl_hkd" label="Unreal. P&L" />
            </th>
            <th className="text-center py-2 pl-4 font-medium text-slate-500">Compliance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(p => {
            const { text: pnlText, positive } = pnl(p.unrealized_pnl_hkd, p.unrealized_pnl_pct)
            return (
              <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                <td className="py-2.5 pr-4 font-mono font-semibold text-slate-800">
                  {p.symbol}
                </td>
                <td className="py-2.5 pr-4 text-slate-500 text-xs">
                  {TYPE_LABELS[p.asset_type] ?? p.asset_type}
                </td>
                <td className="py-2.5 pr-4 text-slate-500 uppercase text-xs">
                  {p.broker}
                </td>
                <td className="py-2.5 pr-4 text-right font-medium tabular-nums">
                  {hkd(p.market_value_hkd)}
                </td>
                <td className="py-2.5 pr-4 text-right text-slate-500 tabular-nums text-xs">
                  {parseFloat(p.quantity).toLocaleString('en-US', { maximumFractionDigits: 4 })}
                </td>
                <td className="py-2.5 pr-4 text-right text-slate-500 tabular-nums text-xs">
                  {p.last_price_hkd ? `$${parseFloat(p.last_price_hkd).toFixed(2)}` : '—'}
                </td>
                <td className={`py-2.5 text-right tabular-nums text-xs font-medium
                  ${positive === true ? 'text-emerald-600' : positive === false ? 'text-red-600' : 'text-slate-400'}`}>
                  {pnlText}
                </td>
                <td className="py-2.5 pl-4 text-center">
                  <ComplianceBadge status={p.compliance_status} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
