"""
Futu OpenD integration via futu-api.

Architecture (from API source inspection):
  - OpenSecTradeContext(filter_trdmarket=TrdMarket.XX) is the unified context.
  - OpenHKTradeContext / OpenUSTradeContext are thin wrappers around it.
  - A-shares held by a Futu HK account via Stock Connect live under TrdMarket.HKCC.
  - Money market funds live under TrdMarket.HKFUND / TrdMarket.USFUND.
  - unlock_trade(password_md5=...) is required before ANY trade API call.

Markets queried for a Futu HK universal margin account:
  HK     — HK equities (SEHK)
  US     — US equities
  HKCC   — A-shares via HK-Shanghai/Shenzhen Stock Connect
  HKFUND — HKD-denominated funds (e.g. E Fund HK Money Market)
  USFUND — USD-denominated funds (e.g. Taikang Kaitai USD Money Market)

Requires:
  - Futu OpenD running (locally or on a server)
  - futu-api Python package installed
  - FUTU_HOST, FUTU_PORT, FUTU_TRADE_PASSWORD_MD5 set in .env

To get the MD5 hash of your trading PIN, run in Terminal:
    echo -n "YOUR_PIN" | md5
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from config import settings

logger = logging.getLogger(__name__)

# For a Futu HK Universal Margin Account, a single OpenSecTradeContext(HK)
# returns ALL positions across all markets. We query one context and use the
# `position_market` field per row to determine currency.
# HKFUND and USFUND are queried separately as they live in a distinct fund sub-account.
_MARKETS = [
    ("HK",     "HK",     "HKD"),   # Universal account: returns HK + US + HKCC positions
    ("HKFUND", "HKFUND", "HKD"),   # HKD money market funds
    ("USFUND", "USFUND", "USD"),   # USD money market funds
]

# Map Futu position_market values → currency
_MARKET_CCY = {
    "HK":     "HKD",
    "US":     "USD",
    "HKCC":   "CNH",
    "SG":     "SGD",
    "JP":     "JPY",
    "CN":     "CNY",
    "HKFUND": "HKD",
    "USFUND": "USD",
}


async def fetch_futu_data() -> dict:
    """
    Connect to Futu OpenD, unlock trade, and return positions + trades
    across all markets for a Futu HK universal account.

    Returns:
      { "positions": [...], "trades": [...], "cash": [...] }
    Raises ValueError if OpenD is unreachable, futu-api not installed,
    or trade password MD5 is not configured.
    """
    try:
        import futu as ft
    except ImportError:
        raise ValueError(
            "futu-api is not installed. Run: pip install futu-api\n"
            "Also ensure Futu OpenD is running."
        )

    if not settings.futu_trade_password_md5:
        raise ValueError(
            "FUTU_TRADE_PASSWORD_MD5 is not set in .env.\n"
            "Run: echo -n 'YOUR_PIN' | md5   and paste the result."
        )

    all_positions: list[dict] = []
    all_trades: list[dict] = []
    cash_by_ccy: dict[str, Decimal] = {}

    for market_str, label, default_ccy in _MARKETS:
        market = getattr(ft.TrdMarket, market_str, None)
        if market is None:
            logger.debug("TrdMarket.%s not found in futu-api — skipping", market_str)
            continue

        try:
            ctx = ft.OpenSecTradeContext(
                filter_trdmarket=market,
                host=settings.futu_host,
                port=settings.futu_port,
            )
        except Exception as e:
            logger.warning("Cannot open Futu %s context: %s", label, e)
            continue

        try:
            # Unlock trade — required for CLI OpenD.
            # GUI OpenD disables API unlock; user must click Unlock in the GUI first.
            # Either way, we attempt unlock and proceed regardless — if already
            # unlocked via GUI, queries will succeed even if this call fails.
            ret, msg = ctx.unlock_trade(password_md5=settings.futu_trade_password_md5)
            if ret != ft.RET_OK:
                gui_disabled = "unlock button" in str(msg).lower() or "disabled" in str(msg).lower()
                if gui_disabled:
                    logger.info(
                        "Futu %s: GUI OpenD requires manual unlock. "
                        "Click the Unlock button in OpenD before syncing.", label
                    )
                    # Still attempt queries — may work if user already unlocked via GUI
                else:
                    logger.warning("Futu %s unlock failed: %s", label, msg)
                    # Still attempt — could be "already unlocked" scenario

            positions = _fetch_positions(ctx, ft, label, default_ccy)
            trades    = _fetch_trades(ctx, ft, label, default_ccy)
            cash      = _fetch_cash(ctx, ft, label, default_ccy)

            all_positions.extend(positions)
            all_trades.extend(trades)

            for c in cash:
                ccy = c["currency"]
                cash_by_ccy[ccy] = cash_by_ccy.get(ccy, Decimal("0")) + c["ending_cash"]

            logger.info(
                "Futu %s: %d positions, %d trades",
                label, len(positions), len(trades),
            )
        except Exception as e:
            logger.warning("Futu %s query error: %s", label, e)
        finally:
            try:
                ctx.close()
            except Exception:
                pass

    combined_cash = [
        {"currency": ccy, "ending_cash": amount}
        for ccy, amount in cash_by_ccy.items()
        if amount != Decimal("0")
    ]

    return {
        "positions": all_positions,
        "trades":    all_trades,
        "cash":      combined_cash,
    }


# ── Per-market query helpers ──────────────────────────────────────────────────

def _fetch_positions(ctx, ft, market: str, default_ccy: str) -> list[dict]:
    ret, data = ctx.position_list_query(trd_env=ft.TrdEnv.REAL)
    if ret != ft.RET_OK:
        logger.warning("Futu %s position query failed: %s", market, data)
        return []
    if data is None or len(data) == 0:
        return []

    positions = []
    for _, row in data.iterrows():
        symbol = str(row.get("code", "")).strip()
        if not symbol:
            continue
        qty = Decimal(str(row.get("qty", 0)))
        if qty == 0:
            continue

        # Prefer the currency field from the API; fall back to market-based lookup
        raw_ccy = str(row.get("currency", "")).upper()
        pos_market = str(row.get("position_market", "")).upper()
        currency = raw_ccy if raw_ccy not in ("", "N/A") else _MARKET_CCY.get(pos_market, default_ccy)

        market_val = Decimal(str(row.get("market_val", 0)))
        cost_price = Decimal(str(row.get("cost_price", 0)))
        name = str(row.get("stock_name", ""))

        positions.append({
            "symbol":          _normalise_symbol(symbol),
            "name":            name,
            "currency":        currency,
            "quantity":        qty,
            "cost_price":      cost_price,
            "current_price":   Decimal(str(row.get("nominal_price", row.get("current_price", 0)))),
            "market_value":    market_val,
            "unrealized_pnl":  Decimal(str(row.get("unrealized_pl", 0))),
            "asset_type_hint": _guess_futu_type(symbol, name),
        })
    return positions


def _fetch_trades(ctx, ft, market: str, default_ccy: str) -> list[dict]:
    """Fetch filled orders from the last 90 days."""
    today = date.today()
    start = today - timedelta(days=90)

    ret, data = ctx.history_order_list_query(
        trd_env=ft.TrdEnv.REAL,
        status_filter_list=[ft.OrderStatus.FILLED_ALL, ft.OrderStatus.FILLED_PART],
        start=start.strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
    )
    if ret != ft.RET_OK or data is None or len(data) == 0:
        return []

    trades = []
    for _, row in data.iterrows():
        symbol = str(row.get("code", "")).strip()
        if not symbol:
            continue
        trade_date = _parse_futu_date(str(row.get("updated_time", "")))
        if not trade_date:
            continue

        qty   = Decimal(str(row.get("dealt_qty", 0)))
        price = Decimal(str(row.get("dealt_avg_price", 0)))
        trd_side = str(row.get("trd_side", "")).upper()
        currency = str(row.get("currency", default_ccy)).upper()
        name = str(row.get("stock_name", ""))

        trades.append({
            "symbol":          _normalise_symbol(symbol),
            "name":            name,
            "currency":        currency,
            "trade_date":      trade_date,
            "tx_type":         "buy" if "BUY" in trd_side else "sell",
            "quantity":        qty,
            "price":           price,
            "gross_amount":    qty * price,
            "fee":             Decimal("0"),
            "asset_type_hint": _guess_futu_type(symbol, name),
        })
    return trades


def _fetch_cash(ctx, ft, market: str, default_ccy: str) -> list[dict]:
    ret, data = ctx.accinfo_query(trd_env=ft.TrdEnv.REAL)
    if ret != ft.RET_OK or data is None or len(data) == 0:
        return []

    cash = []
    for _, row in data.iterrows():
        currency = str(row.get("currency", default_ccy)).upper()
        if currency in ("N/A", ""):
            currency = default_ccy
        cash_val = row.get("cash", 0)
        try:
            cash_decimal = Decimal(str(cash_val))
        except Exception:
            continue
        if cash_decimal != 0:
            cash.append({"currency": currency, "ending_cash": cash_decimal})
    return cash


# ── Symbol normalisation ──────────────────────────────────────────────────────

def _normalise_symbol(symbol: str) -> str:
    """
    Convert Futu's MARKET.CODE prefix format to our canonical format.

    Futu format   → Canonical
    HK.02799      → 2799          (strip leading zeros, drop HK prefix)
    US.TLT        → TLT           (drop US prefix)
    SH.512170     → 512170.SH     (swap to suffix — matches IBKR/compliance format)
    SZ.159915     → 159915.SZ
    SG.D05        → D05.SG
    JP.7203       → 7203.JP
    HK0000857273  → HK0000857273  (ISIN fund codes: keep as-is)
    """
    sym = symbol.strip().upper()

    # ISIN fund codes (2 alpha + 10 digits, no dot)
    if re.match(r'^[A-Z]{2}\d{10}$', sym):
        return sym

    if '.' in sym:
        prefix, code = sym.split('.', 1)
        if prefix == 'HK':
            # Strip leading zeros from numeric HK codes
            return str(int(code)) if code.isdigit() else code
        elif prefix == 'US':
            return code
        elif prefix in ('SH', 'SZ'):
            return f"{code}.{prefix}"   # e.g. 512170.SH
        elif prefix == 'SG':
            return f"{code}.SG"
        elif prefix == 'JP':
            return f"{code}.JP"
        else:
            return code  # Unknown prefix — just use the code part

    return sym


# ── Asset type detection ──────────────────────────────────────────────────────

def _guess_futu_type(symbol: str, name: str) -> str:
    """Infer asset type from Futu's raw MARKET.CODE format and stock name."""
    sym = symbol.upper().strip()
    desc = name.lower()

    # ISIN fund codes → money market
    if re.match(r'^[A-Z]{2}\d{10}$', sym):
        return "money_market"
    # Money market keywords in name
    if any(kw in desc for kw in ("money market", "liquidity fund", "cash fund")):
        return "money_market"

    # Extract market prefix and code
    prefix, code = (sym.split('.', 1) + [''])[:2] if '.' in sym else ('', sym)

    # A-shares (SH/SZ prefix): ETF vs stock by code range
    if prefix in ('SH', 'SZ'):
        if code.startswith(("5", "15", "16", "18")):
            return "etf"
        return "stock"

    # HK stocks
    if prefix == 'HK':
        return "stock"

    # US: ETF keywords in name, otherwise stock
    if prefix == 'US':
        if any(kw in desc for kw in ("etf", "fund", "index", "trust", "ishares",
                                      "vanguard", "spdr", "invesco", "xtrackers")):
            return "etf"
        return "stock"

    # Fallback: ETF keywords in name
    if any(kw in desc for kw in ("etf", "index fund", "tracker fund", "ishares",
                                  "vanguard", "spdr", "invesco")):
        return "etf"
    return "stock"


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_futu_date(date_str: str) -> date | None:
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19], fmt).date()
        except ValueError:
            continue
    return None
