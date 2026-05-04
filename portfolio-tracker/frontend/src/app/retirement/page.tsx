'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer, Cell
} from 'recharts'
import { api } from '@/lib/api'
import { PortfolioSummary } from '@/types/portfolio'
import KpiCard from '@/components/KpiCard'
import AiInsights from '@/components/AiInsights'

const DEFAULT_TARGET_ALLOC: Record<string, number> = {
  etf_broad_index: 40,
  bond_ust: 25,
  crypto: 20,
  etf_commodity: 10,
  cash: 5,
}

const ASSET_LABELS: Record<string, string> = {
  etf_broad_index: 'Index ETFs',
  bond_ust: 'Bonds (UST)',
  crypto: 'Crypto',
  etf_commodity: 'Commodity ETFs',
  cash: 'Cash',
  etf_bond: 'Bond ETFs',
  bond_ukt: 'UK Gilts',
  bond_acgb: 'AU Bonds',
  stock: 'Stocks',
  etf_sector: 'Sector ETFs',
  etf_thematic: 'Thematic ETFs',
}

const USD_HKD_RATE = 7.78
const USD_TARGET = 10_000_000
const TARGET_HKD = USD_TARGET * USD_HKD_RATE

function formatHKD(v: number): string {
  if (v >= 1_000_000) return `HK$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `HK$${(v / 1_000).toFixed(0)}K`
  return `HK$${Math.round(v)}`
}

function formatUSD(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${Math.round(v)}`
}

interface ProjectionPoint {
  year: number
  valueHKD: number
  valueUSD: number
}

export default function RetirementPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [monthlySavings, setMonthlySavings] = useState(140_000)
  const [annualReturn, setAnnualReturn] = useState(7)
  const [includeBonus, setIncludeBonus] = useState(false)
  const [bonusAmount, setBonusAmount] = useState(1_000_000)

  const [targetAlloc, setTargetAlloc] = useState<Record<string, number>>(() => {
    if (typeof window === 'undefined') return DEFAULT_TARGET_ALLOC
    const stored = localStorage.getItem('retirement_target_alloc')
    return stored ? JSON.parse(stored) : DEFAULT_TARGET_ALLOC
  })

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await api.getPortfolioSummary()
        setSummary(data)
      } catch (err: any) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [])

  useEffect(() => {
    localStorage.setItem('retirement_target_alloc', JSON.stringify(targetAlloc))
  }, [targetAlloc])

  const currentNavHKD = useMemo(() => {
    if (!summary) return 0
    return parseFloat(summary.total_nav_hkd || '0')
  }, [summary])

  const currentNavUSD = useMemo(() => currentNavHKD / USD_HKD_RATE, [currentNavHKD])

  // Compute projection (44 years monthly, sample yearly - 2026 to 2070)
  const projection = useMemo(() => {
    const result: ProjectionPoint[] = []
    let balance = currentNavHKD
    const r_monthly = annualReturn / 100 / 12

    const startYear = new Date().getFullYear()

    for (let month = 0; month <= 44 * 12; month++) {
      balance = balance * (1 + r_monthly) + monthlySavings
      if (month > 0 && month % 12 === 0 && includeBonus) {
        balance += bonusAmount
      }

      // Sample yearly
      if (month > 0 && month % 12 === 0) {
        const yearFromNow = month / 12
        const calendarYear = startYear + yearFromNow
        result.push({
          year: yearFromNow,
          calendarYear: Math.round(calendarYear),
          valueHKD: balance,
          valueUSD: balance / USD_HKD_RATE,
        })
      }
    }

    return result
  }, [currentNavHKD, monthlySavings, annualReturn, includeBonus, bonusAmount])

  const goalProjection = useMemo(() => {
    return projection.find(p => p.valueHKD >= TARGET_HKD) ?? null
  }, [projection])

  const yearsToGoal = useMemo(() => {
    if (!goalProjection) return null
    return Math.round(goalProjection.year)
  }, [goalProjection])

  // Calculate actual allocation percentages
  const actualAlloc = useMemo(() => {
    if (!summary) return {}
    const result: Record<string, number> = {}
    const total = currentNavHKD
    if (total === 0) return result

    for (const [k, v] of Object.entries(summary.by_asset_type)) {
      result[k] = (parseFloat(v) / total) * 100
    }
    return result
  }, [summary, currentNavHKD])

  // Comparison chart data
  const comparisonData = useMemo(() => {
    const classes = Object.keys(DEFAULT_TARGET_ALLOC)
    return classes.map(key => ({
      name: ASSET_LABELS[key] || key,
      actual: parseFloat((actualAlloc[key] || 0).toFixed(1)),
      target: targetAlloc[key] || 0,
    }))
  }, [actualAlloc, targetAlloc])

  // Gap analysis
  const gapAnalysis = useMemo(() => {
    return comparisonData.map(row => ({
      ...row,
      gap: parseFloat((row.actual - row.target).toFixed(1)),
    }))
  }, [comparisonData])

  const allocSum = useMemo(() => {
    return Object.values(targetAlloc).reduce((a, b) => a + b, 0)
  }, [targetAlloc])

  // Back-calculation: monthly savings needed for 20-yr goal
  const monthlySavingsFor20Yr = useMemo(() => {
    const n_months = 20 * 12
    const r_monthly = annualReturn / 100 / 12
    const fv = TARGET_HKD

    // FV = PV * (1+r)^n + PMT * (((1+r)^n - 1) / r)
    // PMT = (FV - PV * (1+r)^n) * r / ((1+r)^n - 1)
    const growth_factor = Math.pow(1 + r_monthly, n_months)
    const pv_component = currentNavHKD * growth_factor
    const pmt = (fv - pv_component) * r_monthly / (growth_factor - 1)
    return Math.max(pmt, 0)
  }, [currentNavHKD, annualReturn])

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Loading…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-5xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Retirement Planning</h1>
          <p className="text-sm text-slate-600">Reach your USD 10M retirement goal • Base: HKD (USD rate: 7.78, pegged)</p>
        </div>

        {/* Projection Section */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Retirement Projection</h2>

          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <KpiCard
              label="Portfolio Today"
              value={formatHKD(currentNavHKD)}
              sub={formatUSD(currentNavUSD)}
              positive={true}
            />
            <KpiCard
              label="Years to Goal"
              value={yearsToGoal ? `${yearsToGoal} yrs` : '–'}
              sub={goalProjection ? `Year ${goalProjection.calendarYear}` : 'Not reached'}
              positive={yearsToGoal !== null && yearsToGoal <= 20}
            />
            <KpiCard
              label="Monthly Savings (20yr)"
              value={formatHKD(monthlySavingsFor20Yr)}
              sub={`for USD 10M by 20 yrs`}
              positive={monthlySavingsFor20Yr <= monthlySavings}
            />
          </div>

          {/* Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 p-4 bg-slate-50 rounded-lg">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-2">
                Monthly Savings: {formatHKD(monthlySavings)}
              </label>
              <input
                type="range"
                min="50000"
                max="500000"
                step="10000"
                value={monthlySavings}
                onChange={(e) => setMonthlySavings(parseInt(e.target.value))}
                className="w-full"
              />
              <div className="text-xs text-slate-500 mt-1">HK$50K–HK$500K</div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-2">
                Annual Return: {annualReturn.toFixed(1)}%
              </label>
              <input
                type="range"
                min="3"
                max="15"
                step="0.5"
                value={annualReturn}
                onChange={(e) => setAnnualReturn(parseFloat(e.target.value))}
                className="w-full"
              />
              <div className="text-xs text-slate-500 mt-1">3%–15%</div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="bonus"
                checked={includeBonus}
                onChange={(e) => setIncludeBonus(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="bonus" className="text-xs font-semibold text-slate-600">
                Include annual bonus
              </label>
            </div>

            {includeBonus && (
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-2">
                  Bonus Amount: {formatHKD(bonusAmount)}
                </label>
                <input
                  type="number"
                  value={bonusAmount}
                  onChange={(e) => setBonusAmount(parseFloat(e.target.value) || 0)}
                  className="w-full px-2 py-1 border border-slate-200 rounded text-sm"
                />
              </div>
            )}
          </div>

          {/* Projection Chart */}
          <div className="bg-slate-50 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={360}>
              <AreaChart data={projection} margin={{ top: 10, right: 30, left: 0, bottom: 30 }}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="year"
                  type="number"
                  stroke="#94a3b8"
                  style={{ fontSize: 12 }}
                  tickFormatter={(yearFromNow) => {
                    const year = new Date().getFullYear() + yearFromNow
                    return year.toString()
                  }}
                  label={{ value: 'Year', position: 'insideBottomRight', offset: -10 }}
                />
                <YAxis
                  stroke="#94a3b8"
                  style={{ fontSize: 12 }}
                  tickFormatter={(v) => `${(v / 1_000_000).toFixed(0)}M`}
                  label={{ value: 'Portfolio Value (HKD)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', border: '1px solid #e2e8f0' }}
                  formatter={(v: number) => [
                    `${formatHKD(v)} / ${formatUSD(v / USD_HKD_RATE)}`,
                    'Value',
                  ]}
                  labelFormatter={(year) => `Year ${year}`}
                />
                <ReferenceLine
                  y={TARGET_HKD}
                  stroke="#ea580c"
                  strokeDasharray="5 5"
                  label={{ value: `USD 10M goal (HK$${(TARGET_HKD / 1_000_000).toFixed(0)}M)`, position: 'insideTopRight', offset: -5, fill: '#ea580c', fontSize: 11 }}
                />
                {goalProjection && (
                  <ReferenceLine
                    x={goalProjection.year}
                    stroke="#16a34a"
                    strokeDasharray="5 5"
                    label={{ value: `Reach goal: Year ${goalProjection.calendarYear}`, position: 'top', fill: '#16a34a', fontSize: 11 }}
                  />
                )}
                <Area type="monotone" dataKey="valueHKD" stroke="#6366f1" fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Allocation Section */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Target Asset Allocation</h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Left: Editable targets */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-slate-600 mb-3">Target Percentages</h3>
              {Object.entries(DEFAULT_TARGET_ALLOC).map(([key, _]) => (
                <div key={key} className="flex items-center gap-2">
                  <label className="text-xs text-slate-600 w-32">{ASSET_LABELS[key] || key}</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={targetAlloc[key] || 0}
                    onChange={(e) =>
                      setTargetAlloc({ ...targetAlloc, [key]: parseFloat(e.target.value) || 0 })
                    }
                    className="w-16 px-2 py-1 border border-slate-200 rounded text-xs"
                  />
                  <span className="text-xs text-slate-500">%</span>
                </div>
              ))}
              <div className={`mt-4 p-2 rounded text-xs font-semibold ${allocSum === 100 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                Total: {allocSum}% {allocSum !== 100 && '(should be 100%)'}
              </div>
              <button
                onClick={() => setTargetAlloc(DEFAULT_TARGET_ALLOC)}
                className="mt-4 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded transition-colors"
              >
                Reset to Defaults
              </button>
            </div>

            {/* Right: Comparison chart */}
            <div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={comparisonData} layout="vertical" margin={{ top: 5, right: 30, left: 120, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" stroke="#94a3b8" style={{ fontSize: 11 }} />
                  <YAxis
                    dataKey="name"
                    type="category"
                    stroke="#94a3b8"
                    style={{ fontSize: 11 }}
                    width={110}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 11, borderRadius: 8 }}
                    formatter={(v: number) => `${v.toFixed(1)}%`}
                  />
                  <Legend />
                  <Bar dataKey="actual" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="target" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Gap Analysis Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-600">Asset Class</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-slate-600">Actual %</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-slate-600">Target %</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-slate-600">Gap</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {gapAnalysis.map((row) => (
                  <tr key={row.name} className="hover:bg-slate-50">
                    <td className="px-4 py-2 text-slate-700">{row.name}</td>
                    <td className="px-4 py-2 text-right text-slate-600">{row.actual.toFixed(1)}%</td>
                    <td className="px-4 py-2 text-right text-slate-600">{row.target.toFixed(1)}%</td>
                    <td className={`px-4 py-2 text-right font-medium ${row.gap > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {row.gap > 0 ? '+' : ''}{row.gap.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Advisor Section */}
        <AiInsights portfolio={summary} />
      </div>
    </div>
  )
}
