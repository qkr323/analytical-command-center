"""
IBKR Flex Web Service integration.

Flow:
  1. POST SendRequest  → get a ReferenceCode
  2. Wait 2s, GET GetStatement with ReferenceCode → XML report
  3. Parse positions, trades, cash from XML
  4. Upsert into DB (same deduplication logic as PDF upload)

Docs: https://www.ibkr.com/en/trading/flex-web-service
"""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

import httpx

from config import settings

# US accounts: ndcdyn, HK/EU accounts: gdcdyn
FLEX_BASE = "https://gdcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
MAX_RETRIES = 15
RETRY_DELAY = 5  # seconds between retries — IBKR can take up to 60s to prepare


# ── Public entry point ────────────────────────────────────────────────────────

async def fetch_flex_report() -> dict:
    """
    Fetch the Flex report from IBKR and return parsed data dict:
      {
        "account_id": str,
        "positions": [IBKRPosition, ...],
        "trades":    [IBKRTrade, ...],
        "cash":      [IBKRCash, ...],
      }
    Raises ValueError if credentials are missing or API returns an error.
    """
    if not settings.ibkr_flex_token or not settings.ibkr_flex_query_id:
        raise ValueError("IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID must be set in .env")

    xml_text = await _download_flex_xml()
    return _parse_flex_xml(xml_text)


# ── IBKR API calls ────────────────────────────────────────────────────────────

async def _download_flex_xml() -> str:
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        # Step 1: request the report
        resp = await client.get(
            f"{FLEX_BASE}/SendRequest",
            params={"t": settings.ibkr_flex_token, "q": settings.ibkr_flex_query_id, "v": "3"},
        )
        resp.raise_for_status()
        ref_root = ET.fromstring(resp.text)

        status = ref_root.findtext("Status", "")
        if status != "Success":
            error = ref_root.findtext("ErrorMessage", resp.text)
            raise ValueError(f"IBKR Flex SendRequest failed: {error}")

        ref_code = ref_root.findtext("ReferenceCode", "")
        # IBKR returns the full GetStatement URL in the Url field — use it directly.
        # (Appending /GetStatement again would double it.)
        stmt_url = ref_root.findtext("Url", f"{FLEX_BASE}/GetStatement")

        if not ref_code:
            raise ValueError("IBKR Flex: no ReferenceCode returned")

        # Step 2: poll until report is ready
        for attempt in range(MAX_RETRIES):
            await asyncio.sleep(RETRY_DELAY)
            stmt_resp = await client.get(
                stmt_url,
                params={"q": ref_code, "t": settings.ibkr_flex_token, "v": "3"},
            )
            stmt_resp.raise_for_status()
            text = stmt_resp.text.strip()

            if not text:
                continue  # Empty response — not ready yet

            try:
                root = ET.fromstring(text)
            except ET.ParseError:
                continue  # Malformed XML — not ready yet

            status = root.findtext("Status", "")
            error_msg = root.findtext("ErrorMessage", "")

            # Success: full report returned
            if "<FlexStatement " in text or root.tag == "FlexQueryResponse":
                return text

            # Still generating
            if status in ("", "Warn") or any(
                phrase in error_msg.lower()
                for phrase in ("not ready", "try again", "in progress", "generating")
            ):
                continue

            # Hard error from IBKR
            if status == "Fail" or error_msg:
                raise ValueError(f"IBKR Flex error: {error_msg or text}")

        raise ValueError(
            f"IBKR Flex: report not ready after {MAX_RETRIES * RETRY_DELAY}s. "
            "IBKR servers may be slow — try again in a few minutes."
        )


# ── XML parsing ───────────────────────────────────────────────────────────────

def _parse_flex_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    # Navigate to FlexStatement (may be nested under FlexStatements)
    stmt = root.find(".//FlexStatement")
    if stmt is None:
        raise ValueError("IBKR Flex: no FlexStatement found in response")

    account_id = stmt.get("accountId", "")

    positions = [_parse_position(el) for el in stmt.findall(".//OpenPosition")]
    trades = [_parse_trade(el) for el in stmt.findall(".//Trade")]
    cash = [_parse_cash(el) for el in stmt.findall(".//CashReportCurrency")]

    # Filter out None values from failed parses
    return {
        "account_id": account_id,
        "positions": [p for p in positions if p],
        "trades": [t for t in trades if t],
        "cash": [c for c in cash if c],
    }


def _parse_position(el: ET.Element) -> dict | None:
    symbol = el.get("symbol", "").strip()
    if not symbol:
        return None

    # IBKR uses 'position' for quantity in OpenPositions (not 'quantity')
    quantity = _decimal(el.get("position") or el.get("quantity", "0"))

    return {
        "symbol": symbol,
        "name": el.get("description", ""),
        "asset_category": el.get("assetCategory", "STK"),
        "currency": el.get("currency", "USD"),
        "quantity": quantity,
        "mark_price": _decimal(el.get("markPrice", "0")),
        "position_value": _decimal(el.get("positionValue", "0")),
        "cost_basis_price": _decimal(el.get("costBasisPrice", "0")),
        "cost_basis_money": _decimal(el.get("costBasisMoney", "0")),
    }


def _parse_trade(el: ET.Element) -> dict | None:
    symbol = el.get("symbol", "").strip()
    date_str = el.get("dateTime") or el.get("tradeDate", "")
    if not symbol or not date_str:
        return None

    trade_date = _parse_ibkr_date(date_str)
    if not trade_date:
        return None

    buy_sell = el.get("buySell", "").upper()

    return {
        "symbol": symbol,
        "name": el.get("description", ""),
        "asset_category": el.get("assetCategory", "STK"),
        "currency": el.get("currency", "USD"),
        "trade_date": trade_date,
        "tx_type": "buy" if buy_sell == "BUY" else "sell",
        "quantity": abs(_decimal(el.get("quantity", "0"))),
        "price": _decimal(el.get("price", "0")),
        "proceeds": _decimal(el.get("proceeds", "0")),     # negative for buys
        "commission": abs(_decimal(el.get("commission", "0"))),
        "net_cash": _decimal(el.get("netCash", "0")),
    }


def _parse_cash(el: ET.Element) -> dict | None:
    currency = el.get("currency", "").strip()
    if not currency or currency == "BASE_SUMMARY":
        return None
    return {
        "currency": currency,
        "ending_cash": _decimal(el.get("endingCash", "0")),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decimal(val: str | None) -> Decimal:
    try:
        return Decimal(str(val).replace(",", "")) if val else Decimal("0")
    except Exception:
        return Decimal("0")


def _parse_ibkr_date(date_str: str) -> date | None:
    """IBKR dates: '20240115' or '20240115;120000'"""
    clean = date_str.split(";")[0].strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def _guess_asset_type(asset_category: str, description: str) -> str:
    """Map IBKR asset categories to our hint_type strings."""
    cat = asset_category.upper()
    desc = description.lower()
    if cat == "BOND":
        return "bond"
    if cat in ("OPT", "IOPT"):
        return "option_single"
    if cat == "FUT":
        return "future_single"
    if cat == "CASH":
        return "cash"
    # STK covers both stocks and ETFs — use description to distinguish
    if any(kw in desc for kw in ("etf", "fund", "index", "trust", "ishares", "vanguard", "spdr", "invesco", "xtrackers", "amundi")):
        return "etf"
    return "stock"


def parse_flex_xml_bytes(xml_bytes: bytes) -> dict:
    """Parse a raw IBKR Flex XML file (e.g. manually downloaded)."""
    return _parse_flex_xml(xml_bytes.decode("utf-8", errors="replace"))
