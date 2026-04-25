'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { PortfolioSummary } from '@/types/portfolio'
import KpiCard from '@/components/KpiCard'
import AllocationChart from '@/components/AllocationChart'
import BrokerChart from '@/components/BrokerChart'
import PositionTable from '@/components/PositionTable'
import SyncPanel from '@/components/SyncPanel'
import Link from 'next/link'

function fmt(v: string | null) {
  if (!v) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return `HK$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export default function DashboardPage() {
  const [data, setData]       = useState<PortfolioSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const summary = await api.getPortfolioSummary()
      setData(summary)
      setLastUpdated(new Date())
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const pnl      = data ? parseFloat(data.total_unrealized_pnl_hkd) : 0
  const pnlPct   = data?.total_unrealized_pnl_pct
    ? `${pnl >= 0 ? '+' : ''}${parseFloat(data.total_unrealized_pnl_pct).toFixed(2)}%`
    : null
  const pnlFmt   = data
    ? `${pnl >= 0 ? '+' : ''}${fmt(data.total_unrealized_pnl_hkd)}`
    : '—'

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        Loading portfolio…
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">
        Failed to load portfolio: {error}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">Dashboard</h1>
        <span className="text-xs text-slate-400">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : ''}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total AUM"
          value={fmt(data.total_nav_hkd)}
        />
        <KpiCard
          label="Cost Basis"
          value={fmt(data.total_cost_hkd)}
        />
        <KpiCard
          label="Unrealized P&L"
          value={pnlFmt}
          positive={pnl >= 0}
        />
        <KpiCard
          label="P&L %"
          value={pnlPct ?? '—'}
          positive={pnl >= 0}
        />
      </div>

      {/* Charts */}
      <div className="grid md:grid-cols-2 gap-4">
        <AllocationChart data={data.by_asset_type} />
        <BrokerChart data={data.by_broker} />
      </div>

      {/* Top Positions */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700">Top Positions</h2>
          <Link href="/positions" className="text-xs text-indigo-600 hover:text-indigo-800 transition-colors">
            View all {data.positions.length} →
          </Link>
        </div>
        <PositionTable positions={data.positions} limit={10} />
      </div>

      {/* Sync */}
      <SyncPanel onDone={load} />
    </div>
  )
}
