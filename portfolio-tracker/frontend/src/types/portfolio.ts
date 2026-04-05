export interface Position {
  id: number
  account_id: number
  account_name: string
  broker: string
  symbol: string
  asset_name: string | null
  asset_type: string
  quantity: string
  avg_cost_hkd: string | null
  last_price_hkd: string | null
  market_value_hkd: string | null
  unrealized_pnl_hkd: string | null
  unrealized_pnl_pct: string | null
  currency: string
  compliance_status: string
}

export interface PortfolioSummary {
  total_nav_hkd: string
  total_cost_hkd: string
  total_unrealized_pnl_hkd: string
  total_unrealized_pnl_pct: string | null
  by_asset_type: Record<string, string>
  by_broker: Record<string, string>
  positions: Position[]
}

export interface SyncResult {
  broker?: string
  positions_imported?: number
  positions_updated?: number
  transactions_imported?: number
  positions_updated_count?: number
  rates_refreshed?: Record<string, string>
  error?: string
  detail?: string
}
