"""
Live price fetching service.

Sources:
  yfinance   — HK stocks, US stocks/ETFs, JP ETFs, A-share ETFs
  CoinGecko  — Crypto (BTC, ETH, ETHW, altcoins)
  Fixed 1.0  — Cash, stablecoins (USDT/BUSD/USDC)

Scheduling:
  Called by APScheduler every 30 minutes (configurable).
  Also callable manually via POST /sync/prices.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.asset import Asset, AssetTypeEnum
from models.position import Position
from services.fx import convert_to_hkd, get_rate

logger = logging.getLogger(__name__)

# ── CoinGecko ID map ──────────────────────────────────────────────────────────
# Maps normalised coin symbol → CoinGecko coin ID.
# For LD-prefixed Binance Earn assets, strip "LD" to get the underlying.
_COINGECKO_IDS: dict[str, str] = {
    "BTC":    "bitcoin",
    "ETH":    "ethereum",
    "BNB":    "binancecoin",
    "SOL":    "solana",
    "ADA":    "cardano",
    "XRP":    "ripple",
    "DOGE":   "dogecoin",
    "AVAX":   "avalanche-2",
    "DOT":    "polkadot",
    "MATIC":  "matic-network",
    "LINK":   "chainlink",
    "UNI":    "uniswap",
    "AAVE":   "aave",
    "ETHW":   "ethereum-pow-iou",
    "ASTR":   "astar",
    "SXT":    "space-and-time",
}

# Stablecoins: price is always 1 USD
_STABLECOINS = {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI", "USDP"}


# ── Public entry point ────────────────────────────────────────────────────────

async def refresh_prices(db: AsyncSession) -> dict:
    """
    Fetch latest prices for all assets that have active positions,
    update last_price on each position, and recalculate HKD market values.

    Returns a summary dict with counts and any per-asset errors.
    """
    # Load all positions with their assets
    result = await db.execute(
        select(Position)
        .options(selectinload(Position.asset))
        .where(Position.quantity > 0)
    )
    positions: Sequence[Position] = result.scalars().all()

    # Group positions by price source
    yf_needed:    dict[str, list[Position]] = {}  # yf_ticker → [Position, ...]
    cg_needed:    dict[str, list[Position]] = {}  # cg_id     → [Position, ...]
    fixed_one:    list[Position]            = []  # price = 1.0 always

    for pos in positions:
        asset = pos.asset
        sym   = asset.symbol

        if asset.asset_type == AssetTypeEnum.CASH:
            fixed_one.append(pos)
            continue

        if asset.asset_type == AssetTypeEnum.CRYPTO:
            # LD-prefixed Binance Earn → use underlying coin
            underlying = sym[2:] if sym.startswith("LD") and len(sym) > 2 else sym
            if underlying in _STABLECOINS:
                fixed_one.append(pos)
                continue
            cg_id = _COINGECKO_IDS.get(underlying)
            if cg_id:
                cg_needed.setdefault(cg_id, []).append(pos)
            else:
                logger.debug("No CoinGecko ID for %s — skipping price", sym)
            continue

        # Everything else: yfinance
        yf_sym = _to_yf_symbol(sym, asset.asset_type, asset.currency)
        if yf_sym:
            yf_needed.setdefault(yf_sym, []).append(pos)
        else:
            logger.debug("No yfinance symbol for %s — skipping price", sym)

    # Fetch prices concurrently
    yf_prices, cg_prices = await asyncio.gather(
        _fetch_yf_prices(list(yf_needed.keys())),
        _fetch_coingecko_prices(list(cg_needed.keys())),
    )

    # Apply prices
    updated = 0
    errors: list[str] = []

    # Fixed-price positions (cash / stablecoins → 1.0 in local currency)
    for pos in fixed_one:
        pos.last_price = Decimal("1")
        pos.last_price_hkd, _ = await convert_to_hkd(db, Decimal("1"), pos.asset.currency)
        updated += 1

    # yfinance prices
    for yf_sym, pos_list in yf_needed.items():
        price = yf_prices.get(yf_sym)
        if price is None:
            errors.append(yf_sym)
            continue
        for pos in pos_list:
            pos.last_price = price
            pos.last_price_hkd, _ = await convert_to_hkd(db, price, pos.asset.currency)
            # Recalculate market value if we don't have a broker-supplied local value
            if not pos.market_value_local or pos.market_value_local == 0:
                pos.market_value_local = pos.quantity * price
            pos.market_value_hkd, _ = await convert_to_hkd(
                db, pos.market_value_local, pos.asset.currency
            )
            updated += 1

    # CoinGecko prices
    for cg_id, pos_list in cg_needed.items():
        price = cg_prices.get(cg_id)
        if price is None:
            errors.append(cg_id)
            continue
        for pos in pos_list:
            pos.last_price = price
            pos.last_price_hkd, _ = await convert_to_hkd(db, price, pos.asset.currency)
            pos.market_value_local = pos.quantity * price
            pos.market_value_hkd, _ = await convert_to_hkd(
                db, pos.market_value_local, pos.asset.currency
            )
            updated += 1

    await db.commit()

    return {
        "positions_updated": updated,
        "price_fetch_errors": errors,
        "yf_tickers":  len(yf_needed),
        "cg_coins":    len(cg_needed),
    }


# ── Symbol conversion ─────────────────────────────────────────────────────────

def _to_yf_symbol(symbol: str, asset_type: AssetTypeEnum, currency: str) -> str | None:
    """
    Map our canonical symbol to a yfinance ticker.

    HK stocks:   "700"        → "0700.HK"
    US stocks:   "BABA"       → "BABA"
    JP ETFs:     "2561.T"     → "2561.T"   (already correct)
    SH A-shares: "512170.SH"  → "512170.SS"
    SZ A-shares: "159915.SZ"  → "159915.SZ"
    SG stocks:   "D05.SG"     → "D05.SI"
    Govt bonds:  UKT/UST/ACGB → None (skip — priced by broker)
    """
    sym = symbol.upper()

    # Direct bonds — skip, broker provides accurate prices
    if asset_type in (
        AssetTypeEnum.BOND_UST,
        AssetTypeEnum.BOND_UKT,
        AssetTypeEnum.BOND_ACGB,
    ):
        return None

    # Already has exchange suffix
    if sym.endswith(".T"):    return sym          # Tokyo
    if sym.endswith(".SS"):   return sym          # Shanghai (already converted)
    if sym.endswith(".SZ"):   return sym          # Shenzhen

    # A-shares stored as XXXXXX.SH → convert to .SS for Yahoo
    if sym.endswith(".SH"):
        return sym[:-3] + ".SS"

    # Singapore
    if sym.endswith(".SG"):
        return sym[:-3] + ".SI"

    # HK equities (numeric, no suffix)
    if currency == "HKD" and sym.replace(".", "").isdigit():
        code = int(sym.lstrip("0") or "0")
        return f"{code:04d}.HK"

    # US-listed tickers (letters only, no suffix)
    if sym.isalpha() or (sym.replace(".", "").isalnum() and "." not in sym):
        return sym

    return None


# ── yfinance fetcher (runs in thread pool — yf is synchronous) ────────────────

async def _fetch_yf_prices(symbols: list[str]) -> dict[str, Decimal]:
    if not symbols:
        return {}
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_yf_fetch, symbols)


def _sync_yf_fetch(symbols: list[str]) -> dict[str, Decimal]:
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — run: pip install yfinance")
        return {}

    prices: dict[str, Decimal] = {}
    try:
        # Batch download: faster than one request per ticker
        tickers_obj = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                fast = tickers_obj.tickers[sym].fast_info
                price = fast.last_price
                if price and price > 0:
                    prices[sym] = Decimal(str(round(price, 6)))
            except Exception as e:
                logger.debug("yfinance price error for %s: %s", sym, e)
    except Exception as e:
        logger.warning("yfinance batch fetch error: %s", e)

    return prices


# ── CoinGecko fetcher ─────────────────────────────────────────────────────────

async def _fetch_coingecko_prices(cg_ids: list[str]) -> dict[str, Decimal]:
    """Fetch USD prices from CoinGecko public API (no key required)."""
    if not cg_ids:
        return {}

    ids_param = ",".join(cg_ids)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ids_param, "vs_currencies": "usd"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("CoinGecko fetch failed: %s", e)
        return {}

    return {
        cg_id: Decimal(str(info["usd"]))
        for cg_id, info in data.items()
        if "usd" in info
    }
