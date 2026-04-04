"""
Binance Spot integration via REST API.

Fetches spot balances and recent trade history.
Prices are pulled from Binance's public ticker endpoint so
market_value is populated without requiring a separate price feed.

Requires:
  - BINANCE_API_KEY and BINANCE_SECRET_KEY set in .env
  - Read-only API key is sufficient (no trading permission needed)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from decimal import Decimal

import httpx

from config import settings

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"

# Balances below this USD-equivalent threshold are treated as dust and skipped.
# We filter after price lookup; before that, skip anything below 0.00001 units.
_UNIT_DUST = Decimal("0.00001")

# Stablecoins are kept as positions but marked as cash equivalents.
_STABLECOINS = {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI", "USDP"}

# Quote currencies to try when fetching trade history, in order of preference.
_QUOTE_CURRENCIES = ("USDT", "BUSD", "USDC", "BTC", "ETH", "BNB")


async def fetch_binance_data() -> dict:
    """
    Connect to Binance REST API and return spot balances + recent trades.

    Returns:
      { "positions": [...], "trades": [...], "cash": [] }
    Raises ValueError if API keys are not configured.
    """
    if not settings.binance_api_key or not settings.binance_secret_key:
        raise ValueError(
            "BINANCE_API_KEY and BINANCE_SECRET_KEY are not set in .env.\n"
            "Create a read-only API key at Binance → Account → API Management."
        )

    # Fetch USDT prices for all assets in one call (public endpoint, no auth needed)
    prices_usd = await _fetch_usdt_prices()

    positions = await _fetch_spot_balances(prices_usd)
    trades    = await _fetch_recent_trades(positions)

    return {
        "positions": positions,
        "trades":    trades,
        "cash":      [],  # Stablecoins appear as positions with asset_type_hint="crypto"
    }


# ── Price lookup ──────────────────────────────────────────────────────────────

async def _fetch_usdt_prices() -> dict[str, Decimal]:
    """Return a {coin: usd_price} map using Binance's public ticker endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BINANCE_BASE}/api/v3/ticker/price")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Binance price fetch failed: %s", e)
        return {}

    prices: dict[str, Decimal] = {}
    for item in data:
        sym = str(item.get("symbol", ""))
        if sym.endswith("USDT"):
            base = sym[:-4]
            try:
                prices[base] = Decimal(str(item["price"]))
            except Exception:
                pass

    # Stablecoins ≈ 1 USD
    for stable in _STABLECOINS:
        prices.setdefault(stable, Decimal("1"))

    return prices


# ── Spot balances ─────────────────────────────────────────────────────────────

async def _fetch_spot_balances(prices_usd: dict[str, Decimal]) -> list[dict]:
    data = await _signed_get("/api/v3/account")

    positions = []
    for bal in data.get("balances", []):
        coin = str(bal.get("asset", "")).upper()
        free   = Decimal(str(bal.get("free",   0)))
        locked = Decimal(str(bal.get("locked", 0)))
        total  = free + locked

        if total < _UNIT_DUST:
            continue

        # LD-prefixed assets are Binance Simple Earn (Flexible) positions.
        # e.g. LDUSDT = flexible USDT savings, LDETH = flexible ETH savings.
        # Use the underlying coin's price for valuation.
        underlying = coin[2:] if coin.startswith("LD") and len(coin) > 2 else coin
        price_usd  = prices_usd.get(underlying, prices_usd.get(coin, Decimal("0")))
        market_value = total * price_usd

        # Skip dust positions (< $1 USD equivalent)
        if price_usd > 0 and market_value < Decimal("1"):
            continue

        positions.append({
            "symbol":          coin,
            "name":            f"{underlying} (Earn)" if underlying != coin else coin,
            "currency":        "USD",
            "quantity":        total,
            "cost_price":      Decimal("0"),
            "current_price":   price_usd,
            "market_value":    market_value,
            "unrealized_pnl":  Decimal("0"),
            "asset_type_hint": "crypto",
        })

    return positions


# ── Trade history ─────────────────────────────────────────────────────────────

async def _fetch_recent_trades(positions: list[dict]) -> list[dict]:
    """
    Fetch up to 100 recent fills per held asset.
    Tries USDT pair first, then other quote currencies.
    """
    held_coins = {p["symbol"] for p in positions}

    trades: list[dict] = []
    for coin in held_coins:
        coin_trades = await _fetch_trades_for_coin(coin)
        trades.extend(coin_trades)

    return trades


async def _fetch_trades_for_coin(coin: str) -> list[dict]:
    for quote in _QUOTE_CURRENCIES:
        if quote == coin:
            continue
        pair = f"{coin}{quote}"
        try:
            raw = await _signed_get("/api/v3/myTrades", {"symbol": pair, "limit": 100})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Invalid symbol — try next quote currency
                continue
            logger.debug("Binance trades error for %s: %s", pair, e)
            continue
        except Exception as e:
            logger.debug("Binance trades error for %s: %s", pair, e)
            continue

        if not raw:
            continue

        result = []
        for t in raw:
            trade_date = _parse_binance_ts(t.get("time", 0))
            if not trade_date:
                continue
            qty        = Decimal(str(t.get("qty",        0)))
            price      = Decimal(str(t.get("price",      0)))
            commission = Decimal(str(t.get("commission", 0)))
            is_buyer   = bool(t.get("isBuyer", False))

            # Convert price to USD: if priced in BTC/ETH/BNB, just use 0
            # (exact USD cost basis can be computed later via the FX table)
            price_usd = price if quote in ("USDT", "BUSD", "USDC", "FDUSD") else Decimal("0")

            result.append({
                "symbol":          coin,
                "name":            coin,
                "currency":        "USD",
                "trade_date":      trade_date,
                "tx_type":         "buy" if is_buyer else "sell",
                "quantity":        qty,
                "price":           price_usd,
                "gross_amount":    qty * price_usd,
                "fee":             commission,
                "asset_type_hint": "crypto",
            })
        return result  # Found trades for this coin; no need to try other quote currencies

    return []


# ── Signed HTTP helper ────────────────────────────────────────────────────────

async def _signed_get(endpoint: str, params: dict | None = None) -> dict | list:
    """Issue a signed GET request to the Binance REST API."""
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(
        settings.binance_secret_key.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    params["signature"] = signature

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BINANCE_BASE}{endpoint}",
            params=params,
            headers={"X-MBX-APIKEY": settings.binance_api_key},
        )
        resp.raise_for_status()
        return resp.json()


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_binance_ts(ts: int):
    from datetime import datetime, timezone
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
    except Exception:
        return None
