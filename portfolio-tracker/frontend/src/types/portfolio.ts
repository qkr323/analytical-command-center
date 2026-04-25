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

export interface BrokerPnl {
  broker: string
  realized_trading_pnl_hkd: string | null
  unrealized_pnl_hkd: string
  estimated_total_trading_pnl_hkd: string | null
  dividend_income_hkd: string | null
  fees_hkd: string | null
  sells_total: number
  sells_included: number
  sells_excluded: number
  data_quality: string
  warnings: string[]
}

export interface PnlTotals {
  realized_trading_pnl_hkd: string | null
  unrealized_pnl_hkd: string
  estimated_total_trading_pnl_hkd: string | null
  dividend_income_hkd: string | null
  fees_hkd: string | null
  calculation_warnings: string[]
}

export interface PnlSummary {
  by_broker: BrokerPnl[]
  totals: PnlTotals
}

export interface DataQuality {
  broker: string
  trades: boolean
  dividends: boolean
  fees: boolean
  deposits: boolean
  withdrawals: boolean
  cost_basis_reliability: string
  warnings: string[]
  trade_count: number
  dividend_count: number
  fee_count: number
  deposit_count: number
  withdrawal_count: number
  earliest_trade_date: string | null
  sells_excluded_count: number
}
