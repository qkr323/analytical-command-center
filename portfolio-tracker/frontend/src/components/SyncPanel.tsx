'use client'

import { useState } from 'react'
import { api } from '@/lib/api'

interface SyncBtn {
  label: string
  key: string
  fn: () => Promise<unknown>
}

const BUTTONS: SyncBtn[] = [
  { label: 'IBKR',    key: 'ibkr',    fn: api.syncIBKR    },
  { label: 'Futu',    key: 'futu',    fn: api.syncFutu    },
  { label: 'Binance', key: 'binance', fn: api.syncBinance },
  { label: 'Prices',  key: 'prices',  fn: api.syncPrices  },
  { label: 'FX',      key: 'fx',      fn: api.syncFX      },
]

interface Props {
  onDone: () => void
}

export default function SyncPanel({ onDone }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

  async function run(btn: SyncBtn) {
    setLoading(btn.key)
    setMessage(null)
    try {
      const res = await btn.fn() as Record<string, unknown>
      const detail = res.detail as string | undefined
      if (detail) throw new Error(detail)

      const pos = (res.positions_updated ?? res.positions_imported ?? 0) as number
      const tx  = (res.transactions_imported ?? 0) as number
      const updated = (res.positions_updated as number | undefined)

      let text = `${btn.label} sync complete.`
      if (btn.key === 'prices')  text = `Prices updated (${pos} positions).`
      else if (btn.key === 'fx') text = `FX rates refreshed.`
      else text = `${btn.label}: ${pos} positions, ${tx} transactions.`

      setMessage({ text, ok: true })
      onDone()
    } catch (e: unknown) {
      const raw = (e as Error).message
      const text = btn.key === 'futu' && raw.includes('not reachable')
        ? 'Futu requires local sync — run from your Mac terminal (see SYNC_INSTRUCTIONS.txt).'
        : `${btn.label} failed: ${raw}`
      setMessage({ text, ok: false })
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-700 mb-3">Sync Data</h2>
      <div className="flex flex-wrap gap-2">
        {BUTTONS.map(btn => (
          <button
            key={btn.key}
            onClick={() => run(btn)}
            disabled={!!loading}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-slate-800 text-white
                       hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            {loading === btn.key ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 000 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z"/>
                </svg>
                {btn.label}…
              </span>
            ) : btn.label}
          </button>
        ))}
      </div>
      {message && (
        <p className={`mt-3 text-sm ${message.ok ? 'text-emerald-600' : 'text-red-600'}`}>
          {message.text}
        </p>
      )}
    </div>
  )
}
