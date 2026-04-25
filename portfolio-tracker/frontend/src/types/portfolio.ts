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
  last_price: string | null
  last_price_hkd: string | null
  market_value_local: string | null
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

export interface Transaction {
  id: number
  account_id: number
  broker: string
  account_name: string
  symbol: string | null
  asset_name: string | null
  asset_type: string | null
  tx_type: string
  trade_date: string
  quantity: string | null
  price: string | null
  gross_amount: string | null
  fee: string
  net_amount: string | null
  currency: string
  gross_amount_hkd: string | null
  fee_hkd: string | null
  net_amount_hkd: string | null
}

export interface NavSnapshot {
  snapshot_date: string
  total_nav_hkd: string
  by_broker: Record<string, string>
  by_asset_type: Record<string, string>
}
