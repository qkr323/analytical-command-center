'use client'

import { useEffect, useState, useCallback } from 'react'
import { api } from '@/lib/api'
import type { Transaction } from '@/types/portfolio'

const BROKERS    = ['', 'ibkr', 'futu', 'binance', 'sofi', 'osl', 'hangseng']
const TX_TYPES   = ['', 'buy', 'sell', 'dividend', 'fee', 'deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'interest']
const CURRENCIES = ['', 'USD', 'HKD', 'CNH', 'BTC', 'ETH', 'BNB']

const TYPE_COLORS: Record<string, string> = {
  buy:           'bg-emerald-50 text-emerald-700',
  sell:          'bg-red-50 text-red-700',
  dividend:      'bg-blue-50 text-blue-700',
  fee:           'bg-slate-100 text-slate-600',
  deposit:       'bg-indigo-50 text-indigo-700',
  withdrawal:    'bg-orange-50 text-orange-700',
  transfer_in:   'bg-teal-50 text-teal-700',
  transfer_out:  'bg-amber-50 text-amber-700',
  interest:      'bg-violet-50 text-violet-700',
}

function amt(v: string | null, ccy: string) {
  if (!v) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return `${ccy} ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function hkd(v: string | null) {
  if (!v) return null
  const n = parseFloat(v)
  if (isNaN(n)) return null
  return `HK$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export default function TransactionsPage() {
  const [txs, setTxs]         = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  const [broker,   setBroker]   = useState('')
  const [symbol,   setSymbol]   = useState('')
  const [currency, setCurrency] = useState('')
  const [txType,   setTxType]   = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo,   setDateTo]   = useState('')
  const [offset,   setOffset]   = useState(0)

  const LIMIT = 200

  const load = useCallback(async (newOffset = 0) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getTransactions({
        broker:    broker    || undefined,
        symbol:    symbol    || undefined,
        currency:  currency  || undefined,
        tx_type:   txType    || undefined,
        date_from: dateFrom  || undefined,
        date_to:   dateTo    || undefined,
        limit:     LIMIT,
        offset:    newOffset,
      })
      setTxs(data)
      setOffset(newOffset)
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [broker, symbol, currency, txType, dateFrom, dateTo])

  useEffect(() => { load(0) }, [load])

  function reset() {
    setBroker(''); setSymbol(''); setCurrency('')
    setTxType(''); setDateFrom(''); setDateTo('')
  }

  const Sel = ({ value, onChange, options, labels }: {
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
          {o === '' ? (labels?.[''] ?? 'All') : (labels?.[o] ?? o)}
        </option>
      ))}
    </select>
  )

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-slate-800">Transactions</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <Sel value={broker} onChange={setBroker} options={BROKERS}
          labels={{ '': 'All Brokers', ibkr: 'IBKR', futu: 'Futu', binance: 'Binance',
                    sofi: 'SoFi', osl: 'OSL', hangseng: 'Hang Seng' }} />
        <Sel value={txType} onChange={setTxType} options={TX_TYPES}
          labels={{ '': 'All Types', buy: 'Buy', sell: 'Sell', dividend: 'Dividend',
                    fee: 'Fee', deposit: 'Deposit', withdrawal: 'Withdrawal',
                    transfer_in: 'Transfer In', transfer_out: 'Transfer Out', interest: 'Interest' }} />
        <Sel value={currency} onChange={setCurrency} options={CURRENCIES}
          labels={{ '': 'All Currencies' }} />

        <input
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          placeholder="Ticker (e.g. AAPL)"
          className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 w-36
                     focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <div className="flex items-center gap-2">
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5
                       focus:outline-none focus:ring-2 focus:ring-indigo-300" />
          <span className="text-slate-400 text-sm">to</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5
                       focus:outline-none focus:ring-2 focus:ring-indigo-300" />
        </div>

        <button onClick={reset}
          className="text-sm text-slate-500 hover:text-slate-700 underline underline-offset-2">
          Reset
        </button>

        <span className="ml-auto text-sm text-slate-500">
          {loading ? 'Loading…' : `${txs.length} transactions`}
        </span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 font-medium text-slate-600">Date</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Type</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Symbol</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Broker</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Qty</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Price</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Gross Amt</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Fee</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Net Amt</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">HKD Equiv</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-slate-400">Loading…</td>
                </tr>
              )}
              {!loading && txs.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-slate-400">No transactions found</td>
                </tr>
              )}
              {txs.map(tx => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-2.5 text-slate-600 tabular-nums text-xs">{tx.trade_date}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                      ${TYPE_COLORS[tx.tx_type] ?? 'bg-slate-100 text-slate-600'}`}>
                      {tx.tx_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono font-semibold text-slate-800">
                    {tx.symbol ?? <span className="text-slate-400 font-sans font-normal text-xs">cash</span>}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 uppercase text-xs">{tx.broker}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 text-xs">
                    {tx.quantity
                      ? parseFloat(tx.quantity).toLocaleString('en-US', { maximumFractionDigits: 4 })
                      : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 text-xs">
                    {tx.price
                      ? `${tx.currency} ${parseFloat(tx.price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
                      : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-xs font-medium">
                    {amt(tx.gross_amount, tx.currency)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-500">
                    {tx.fee && parseFloat(tx.fee) > 0 ? amt(tx.fee, tx.currency) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-xs font-medium">
                    {amt(tx.net_amount ?? tx.gross_amount, tx.currency)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-500">
                    {hkd(tx.net_amount_hkd ?? tx.gross_amount_hkd) ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!loading && (
          <div className="border-t border-slate-100 px-4 py-3 flex items-center justify-between">
            <button
              onClick={() => load(Math.max(0, offset - LIMIT))}
              disabled={offset === 0}
              className="text-sm text-slate-600 hover:text-slate-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <span className="text-xs text-slate-400">
              Showing {offset + 1}–{offset + txs.length}
            </span>
            <button
              onClick={() => load(offset + LIMIT)}
              disabled={txs.length < LIMIT}
              className="text-sm text-slate-600 hover:text-slate-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
