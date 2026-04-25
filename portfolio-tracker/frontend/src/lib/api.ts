/**
 * API client — calls Next.js proxy routes, which forward to the backend
 * with the API key attached server-side.
 */

const BASE = '/api/proxy'

type Params = Record<string, string | number | boolean | undefined | null>

async function request<T>(
  path: string,
  method: 'GET' | 'POST' = 'GET',
  params?: Params,
): Promise<T> {
  let url = `${BASE}/${path}`
  if (params) {
    const search = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') search.set(k, String(v))
    }
    const qs = search.toString()
    if (qs) url += `?${qs}`
  }
  const res = await fetch(url, { method, cache: 'no-store' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  getPortfolioSummary: () =>
    request<import('@/types/portfolio').PortfolioSummary>('portfolio/summary'),

  getTransactions: (params?: Params) =>
    request<import('@/types/portfolio').Transaction[]>('transactions', 'GET', params),

  getNavHistory: () =>
    request<import('@/types/portfolio').NavSnapshot[]>('history/snapshots'),

  getPnlSummary: () =>
    request<import('@/types/portfolio').PnlSummary>('pnl/summary'),

  getDataQuality: () =>
    request<import('@/types/portfolio').DataQuality[]>('pnl/data-quality'),

  recalculatePnl: () =>
    request<{ groups_processed: number; status: string }>('pnl/recalculate', 'POST'),

  syncIBKR:   () => request<import('@/types/portfolio').SyncResult>('sync/ibkr',   'POST'),
  syncFutu:   () => request<import('@/types/portfolio').SyncResult>('sync/futu',   'POST'),
  syncBinance:() => request<import('@/types/portfolio').SyncResult>('sync/binance','POST'),
  syncPrices: () => request<import('@/types/portfolio').SyncResult>('sync/prices', 'POST'),
  syncFX:     () => request<import('@/types/portfolio').SyncResult>('sync/fx',     'POST'),
}
