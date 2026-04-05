'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { PortfolioSummary, Position } from '@/types/portfolio'
import PositionTable from '@/components/PositionTable'
import ComplianceBadge from '@/components/ComplianceBadge'

const BROKERS    = ['all', 'ibkr', 'futu', 'binance', 'sofi', 'osl']
const TYPES      = ['all', 'stock', 'etf_bond', 'etf_broad_index', 'etf_commodity', 'crypto', 'cash', 'bond_ust', 'bond_ukt']
const COMPLIANCE = ['all', 'allowed', 'legacy_hold', 'review_required', 'blocked']

const TYPE_LABELS: Record<string, string> = {
  stock: 'Stock', etf_bond: 'Bond ETF', etf_broad_index: 'Index ETF',
  etf_commodity: 'Commodity ETF', crypto: 'Crypto', cash: 'Cash',
  bond_ust: 'US Treasury', bond_ukt: 'UK Gilt',
}

export default function PositionsPage() {
  const [data, setData]         = useState<PortfolioSummary | null>(null)
  const [loading, setLoading]   = useState(true)
  const [broker, setBroker]     = useState('all')
  const [assetType, setType]    = useState('all')
  const [compliance, setComp]   = useState('all')

  useEffect(() => {
    api.getPortfolioSummary()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  const filtered: Position[] = data?.positions.filter(p => {
    if (broker !== 'all'     && p.broker !== broker)              return false
    if (assetType !== 'all'  && p.asset_type !== assetType)       return false
    if (compliance !== 'all' && p.compliance_status !== compliance) return false
    return true
  }) ?? []

  const totalValue = filtered.reduce((s, p) => s + parseFloat(p.market_value_hkd ?? '0'), 0)

  const FilterSelect = ({
    value, onChange, options, labels,
  }: {
    value: string
    onChange: (v: string) => void
    options: string[]
    labels?: Record<string, string>
  }) => (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700
                 focus:outline-none focus:ring-2 focus:ring-indigo-300"
    >
      {options.map(o => (
        <option key={o} value={o}>
          {o === 'all' ? 'All' : (labels?.[o] ?? o.replace('_', ' '))}
        </option>
      ))}
    </select>
  )

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-slate-800">All Positions</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center gap-3">
        <span className="text-sm text-slate-500 font-medium">Filter:</span>
        <FilterSelect
          value={broker} onChange={setBroker}
          options={BROKERS}
          labels={{ ibkr: 'IBKR', futu: 'Futu', binance: 'Binance', sofi: 'SoFi', osl: 'OSL' }}
        />
        <FilterSelect
          value={assetType} onChange={setType}
          options={TYPES}
          labels={TYPE_LABELS}
        />
        <FilterSelect
          value={compliance} onChange={setComp}
          options={COMPLIANCE}
        />
        <span className="ml-auto text-sm text-slate-500">
          {filtered.length} position{filtered.length !== 1 ? 's' : ''} ·
          HK${(totalValue / 1_000_000).toFixed(2)}M
        </span>
      </div>

      {/* Compliance summary chips */}
      {data && (
        <div className="flex flex-wrap gap-2">
          {COMPLIANCE.slice(1).map(c => {
            const count = data.positions.filter(p => p.compliance_status === c).length
            if (!count) return null
            return (
              <button
                key={c}
                onClick={() => setComp(compliance === c ? 'all' : c)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-colors
                  ${compliance === c ? 'ring-2 ring-offset-1 ring-indigo-400' : ''}`}
              >
                <ComplianceBadge status={c} />
                <span className="text-slate-500">{count}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        {loading ? (
          <div className="text-sm text-slate-400 py-8 text-center">Loading…</div>
        ) : (
          <PositionTable positions={filtered} />
        )}
      </div>
    </div>
  )
}
