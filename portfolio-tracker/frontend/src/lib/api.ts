/**
 * API client — calls Next.js proxy routes, which forward to the backend
 * with the API key attached server-side.
 */

const BASE = '/api/proxy'

async function request<T>(
  path: string,
  method: 'GET' | 'POST' = 'GET',
): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, {
    method,
    cache: 'no-store',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  getPortfolioSummary: () =>
    request<import('@/types/portfolio').PortfolioSummary>('portfolio/summary'),

  syncIBKR:   () => request<import('@/types/portfolio').SyncResult>('sync/ibkr',   'POST'),
  syncFutu:   () => request<import('@/types/portfolio').SyncResult>('sync/futu',   'POST'),
  syncBinance:() => request<import('@/types/portfolio').SyncResult>('sync/binance','POST'),
  syncPrices: () => request<import('@/types/portfolio').SyncResult>('sync/prices', 'POST'),
  syncFX:     () => request<import('@/types/portfolio').SyncResult>('sync/fx',     'POST'),
}
