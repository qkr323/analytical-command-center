'use client'

import type { DataQuality } from '@/types/portfolio'

const RELIABILITY_CONFIG = {
  high:         { label: 'Complete',     bg: 'bg-emerald-50',  border: 'border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  partial:      { label: 'Partial',      bg: 'bg-amber-50',    border: 'border-amber-200',   text: 'text-amber-700',   dot: 'bg-amber-400'   },
  experimental: { label: 'Experimental', bg: 'bg-orange-50',   border: 'border-orange-200',  text: 'text-orange-700',  dot: 'bg-orange-400'  },
  unknown:      { label: 'Unknown',      bg: 'bg-slate-50',    border: 'border-slate-200',   text: 'text-slate-600',   dot: 'bg-slate-400'   },
}

function Check({ ok }: { ok: boolean }) {
  return ok
    ? <span className="text-emerald-500 text-xs">✓</span>
    : <span className="text-slate-300 text-xs">✗</span>
}

interface Props {
  items: DataQuality[]
}

export default function DataQualityBanner({ items }: Props) {
  return (
    <div className="flex flex-col gap-3">
      {items.map(dq => {
        const cfg = RELIABILITY_CONFIG[dq.cost_basis_reliability as keyof typeof RELIABILITY_CONFIG]
          ?? RELIABILITY_CONFIG.unknown
        return (
          <div key={dq.broker} className={`rounded-xl border ${cfg.bg} ${cfg.border} p-4`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                <span className="font-semibold text-sm text-slate-800 uppercase">{dq.broker}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.border} ${cfg.text} font-medium`}>
                  {cfg.label}
                </span>
              </div>
              <span className="text-xs text-slate-400">
                {dq.trade_count} trades
                {dq.earliest_trade_date ? ` · from ${dq.earliest_trade_date}` : ''}
                {dq.sells_excluded_count > 0
                  ? ` · ${dq.sells_excluded_count} sell${dq.sells_excluded_count !== 1 ? 's' : ''} excluded`
                  : ''}
              </span>
            </div>

            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 mb-2">
              <span><Check ok={dq.trades} /> Trades</span>
              <span><Check ok={dq.dividends} /> Dividends</span>
              <span><Check ok={dq.fees} /> Fees</span>
              <span><Check ok={dq.deposits} /> Deposits</span>
              <span><Check ok={dq.withdrawals} /> Withdrawals</span>
            </div>

            {dq.warnings.length > 0 && (
              <ul className={`text-xs ${cfg.text} space-y-0.5`}>
                {dq.warnings.map((w, i) => (
                  <li key={i}>⚠ {w}</li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
