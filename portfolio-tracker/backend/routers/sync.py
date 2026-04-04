"""
Broker sync endpoints.

POST /sync/ibkr    — pull latest positions + trades from IBKR Flex
POST /sync/futu    — pull latest positions + trades from Futu OpenD
GET  /sync/status  — last sync time per broker
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.account import Account, BrokerEnum
from models.asset import Asset, AssetTypeEnum, ComplianceStatusEnum
from models.compliance_review import ComplianceReview, ReviewStatusEnum
from models.position import Position
from models.position_snapshot import PositionSnapshot
from models.transaction import Transaction, TransactionTypeEnum
from services.brokers.ibkr_flex import fetch_flex_report, parse_flex_xml_bytes, _guess_asset_type as ibkr_guess_type
from services.brokers.futu_opend import fetch_futu_data
from services.brokers.binance_api import fetch_binance_data
from services.compliance import check_symbol
from services.fx import convert_to_hkd, refresh_rates
from routers.upload import _get_or_create_asset, _tx_fingerprint
from services.parsers.base import RawTransaction

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/ibkr")
async def sync_ibkr(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Pull latest data from IBKR Flex Web Service and upsert into DB."""

    # Get IBKR account
    account = await db.scalar(select(Account).where(Account.broker == BrokerEnum.IBKR))
    if not account:
        raise HTTPException(404, "No IBKR account found. Create one first via POST /accounts/")

    try:
        report = await fetch_flex_report()
    except ValueError as e:
        raise HTTPException(400, str(e))

    snapshot_date = date.today()
    summary: dict[str, Any] = {
        "broker": "ibkr",
        "account_id": account.id,
        "synced_at": datetime.utcnow().isoformat(),
        "positions_imported": 0,
        "positions_updated": 0,
        "transactions_imported": 0,
        "transactions_skipped_duplicate": 0,
        "flagged_for_review": [],
        "blocked": [],
        "legacy_hold": [],
    }

    # Process positions
    for pos in report["positions"]:
        await _upsert_position_from_ibkr(db, account.id, pos, snapshot_date, summary)

    # Process cash balances as positions
    for cash in report["cash"]:
        await _upsert_cash(db, account.id, cash, snapshot_date, summary)

    # Process trades
    for trade in report["trades"]:
        await _upsert_trade_from_ibkr(db, account.id, trade, summary)

    await db.commit()
    summary.pop("_seen", None)
    return summary


@router.post("/ibkr/xml")
async def sync_ibkr_xml(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a manually downloaded IBKR Flex XML file instead of using the API."""

    account = await db.scalar(select(Account).where(Account.broker == BrokerEnum.IBKR))
    if not account:
        raise HTTPException(404, "No IBKR account found. Create one first via POST /accounts/")

    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(400, "Only XML files are accepted")

    xml_bytes = await file.read()

    try:
        report = parse_flex_xml_bytes(xml_bytes)
    except Exception as e:
        raise HTTPException(422, f"Failed to parse IBKR XML: {e}")

    snapshot_date = date.today()
    summary: dict[str, Any] = {
        "broker": "ibkr",
        "account_id": account.id,
        "synced_at": datetime.utcnow().isoformat(),
        "ibkr_account": report.get("account_id", ""),
        "positions_imported": 0,
        "positions_updated": 0,
        "transactions_imported": 0,
        "transactions_skipped_duplicate": 0,
        "flagged_for_review": [],
        "blocked": [],
        "legacy_hold": [],
    }

    for pos in report["positions"]:
        await _upsert_position_from_ibkr(db, account.id, pos, snapshot_date, summary)

    for cash in report["cash"]:
        await _upsert_cash(db, account.id, cash, snapshot_date, summary)

    for trade in report["trades"]:
        await _upsert_trade_from_ibkr(db, account.id, trade, summary)

    await db.commit()
    summary.pop("_seen", None)
    return summary


@router.post("/futu")
async def sync_futu(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Pull latest data from Futu OpenD and upsert into DB."""

    account = await db.scalar(select(Account).where(Account.broker == BrokerEnum.FUTU))
    if not account:
        raise HTTPException(404, "No Futu account found. Create one first via POST /accounts/")

    try:
        data = await fetch_futu_data()
    except ValueError as e:
        raise HTTPException(400, str(e))

    snapshot_date = date.today()
    summary: dict[str, Any] = {
        "broker": "futu",
        "account_id": account.id,
        "synced_at": datetime.utcnow().isoformat(),
        "positions_imported": 0,
        "positions_updated": 0,
        "transactions_imported": 0,
        "transactions_skipped_duplicate": 0,
        "flagged_for_review": [],
        "blocked": [],
        "legacy_hold": [],
    }

    for pos in data["positions"]:
        await _upsert_position_from_futu(db, account.id, pos, snapshot_date, summary)

    for cash in data["cash"]:
        await _upsert_cash(db, account.id, cash, snapshot_date, summary)

    for trade in data["trades"]:
        await _upsert_trade_from_futu(db, account.id, trade, summary)

    await db.commit()
    summary.pop("_seen", None)
    return summary


@router.get("/futu/debug")
async def debug_futu() -> dict[str, Any]:
    """
    Step through Futu OpenD API calls and return raw results for each market.
    Does NOT write to the database.
    """
    import futu as ft
    from config import settings

    result: dict[str, Any] = {
        "host": settings.futu_host,
        "port": settings.futu_port,
        "markets": {},
    }

    if not settings.futu_trade_password_md5:
        result["error"] = "FUTU_TRADE_PASSWORD_MD5 not set in .env"
        return result

    markets = [
        (ft.TrdMarket.HK,     "HK"),
        (ft.TrdMarket.US,     "US"),
        (ft.TrdMarket.HKCC,   "HKCC"),
        (ft.TrdMarket.HKFUND, "HKFUND"),
        (ft.TrdMarket.USFUND, "USFUND"),
    ]

    for market, label in markets:
        market_result: dict[str, Any] = {}
        try:
            ctx = ft.OpenSecTradeContext(
                filter_trdmarket=market,
                host=settings.futu_host,
                port=settings.futu_port,
            )

            # Unlock
            ret_ul, msg_ul = ctx.unlock_trade(password_md5=settings.futu_trade_password_md5)
            market_result["unlock_ret"] = str(ret_ul)
            market_result["unlock_msg"] = str(msg_ul)

            if ret_ul == ft.RET_OK:
                ret, data = ctx.position_list_query(trd_env=ft.TrdEnv.REAL)
                market_result["position_query_ret"] = str(ret)
                if ret == ft.RET_OK and data is not None:
                    market_result["position_count"] = len(data)
                    market_result["positions_sample"] = data.head(3).to_dict(orient="records") if len(data) > 0 else []
                else:
                    market_result["position_error"] = str(data)

                ret2, data2 = ctx.accinfo_query(trd_env=ft.TrdEnv.REAL)
                market_result["accinfo_ret"] = str(ret2)
                if ret2 == ft.RET_OK and data2 is not None:
                    market_result["accinfo_cash"] = {
                        str(r.get("currency", "?")): str(r.get("cash", 0))
                        for _, r in data2.iterrows()
                    }

            ctx.close()
        except Exception as e:
            market_result["exception"] = str(e)

        result["markets"][label] = market_result

    return result


@router.post("/binance")
async def sync_binance(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Pull latest spot balances + trades from Binance and upsert into DB."""

    account = await db.scalar(select(Account).where(Account.broker == BrokerEnum.BINANCE))
    if not account:
        raise HTTPException(404, "No Binance account found. Create one first via POST /accounts/")

    try:
        data = await fetch_binance_data()
    except ValueError as e:
        raise HTTPException(400, str(e))

    snapshot_date = date.today()
    summary: dict[str, Any] = {
        "broker": "binance",
        "account_id": account.id,
        "synced_at": datetime.utcnow().isoformat(),
        "positions_imported": 0,
        "positions_updated": 0,
        "transactions_imported": 0,
        "transactions_skipped_duplicate": 0,
        "flagged_for_review": [],
        "blocked": [],
        "legacy_hold": [],
    }

    for pos in data["positions"]:
        await _upsert_position_from_binance(db, account.id, pos, snapshot_date, summary)

    for trade in data["trades"]:
        await _upsert_trade_from_binance(db, account.id, trade, summary)

    await db.commit()
    summary.pop("_seen", None)
    return summary


@router.get("/ibkr/debug")
async def debug_ibkr_flex() -> dict[str, Any]:
    """
    Step through the IBKR Flex Web Service handshake and return the raw
    responses at each stage — useful for diagnosing query configuration issues.
    Does NOT write anything to the database.
    """
    import httpx, xml.etree.ElementTree as ET
    from config import settings

    FLEX_BASE = "https://gdcdyn.interactivebrokers.com/AccountManagement/FlexWebService"

    if not settings.ibkr_flex_token or not settings.ibkr_flex_query_id:
        return {"error": "IBKR_FLEX_TOKEN or IBKR_FLEX_QUERY_ID not set in .env"}

    result: dict[str, Any] = {
        "token_prefix": settings.ibkr_flex_token[:8] + "...",
        "query_id": settings.ibkr_flex_query_id,
        "step1_send_request": {},
        "step2_get_statement": {},
    }

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        # Step 1
        try:
            resp = await client.get(
                f"{FLEX_BASE}/SendRequest",
                params={"t": settings.ibkr_flex_token, "q": settings.ibkr_flex_query_id, "v": "3"},
            )
            result["step1_send_request"]["http_status"] = resp.status_code
            result["step1_send_request"]["raw_response"] = resp.text[:2000]

            ref_root = ET.fromstring(resp.text)
            result["step1_send_request"]["Status"] = ref_root.findtext("Status", "")
            result["step1_send_request"]["ErrorMessage"] = ref_root.findtext("ErrorMessage", "")
            result["step1_send_request"]["ReferenceCode"] = ref_root.findtext("ReferenceCode", "")
            result["step1_send_request"]["Url"] = ref_root.findtext("Url", "")

            ref_code = ref_root.findtext("ReferenceCode", "")
            stmt_url = ref_root.findtext("Url", f"{FLEX_BASE}/GetStatement")

            if not ref_code or ref_root.findtext("Status", "") != "Success":
                result["diagnosis"] = "SendRequest failed — check token and query ID"
                return result
        except Exception as exc:
            result["step1_send_request"]["error"] = str(exc)
            result["diagnosis"] = "SendRequest threw an exception"
            return result

        result["step2_get_statement"]["url_used"] = stmt_url

        # Step 2: single attempt after 5s
        import asyncio
        await asyncio.sleep(5)
        try:
            stmt_resp = await client.get(
                stmt_url,
                params={"q": ref_code, "t": settings.ibkr_flex_token, "v": "3"},
            )
            result["step2_get_statement"]["http_status"] = stmt_resp.status_code
            result["step2_get_statement"]["raw_response"] = stmt_resp.text[:2000]

            text = stmt_resp.text.strip()
            if text:
                try:
                    root = ET.fromstring(text)
                    result["step2_get_statement"]["Status"] = root.findtext("Status", "")
                    result["step2_get_statement"]["ErrorCode"] = root.findtext("ErrorCode", "")
                    result["step2_get_statement"]["ErrorMessage"] = root.findtext("ErrorMessage", "")
                    result["step2_get_statement"]["root_tag"] = root.tag
                except ET.ParseError as pe:
                    result["step2_get_statement"]["parse_error"] = str(pe)
        except Exception as exc:
            result["step2_get_statement"]["error"] = str(exc)

    return result


@router.post("/fx")
async def sync_fx_rates(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Refresh FX rates from frankfurter.app for today, then recalculate HKD
    values for every position whose cost_currency is not HKD.
    """
    rates = await refresh_rates(db)

    # Recalculate all non-HKD positions
    result = await db.execute(
        select(Position)
        .options(selectinload(Position.asset))
        .where(Position.quantity > 0)
    )
    positions = result.scalars().all()

    updated = 0
    for pos in positions:
        ccy = (pos.cost_currency or "HKD").upper()
        if ccy == "HKD":
            continue

        # CNH proxied through CNY
        lookup_ccy = "CNY" if ccy == "CNH" else ccy
        fx = rates.get(lookup_ccy) or rates.get(ccy)
        if fx is None:
            continue

        if pos.last_price is not None:
            pos.last_price_hkd = pos.last_price * fx
        if pos.avg_cost is not None:
            pos.avg_cost_hkd = pos.avg_cost * fx

        # Use stored local-currency values for monetary fields — avoids
        # price-per-100 issues with bonds where quantity ≠ face*price.
        if pos.market_value_local is not None:
            pos.market_value_hkd = pos.market_value_local * fx
        elif pos.last_price_hkd is not None:
            pos.market_value_hkd = pos.quantity * pos.last_price_hkd

        if pos.total_cost_local is not None:
            pos.total_cost_hkd = pos.total_cost_local * fx
        elif pos.avg_cost_hkd is not None:
            pos.total_cost_hkd = pos.quantity * pos.avg_cost_hkd

        if pos.total_cost_hkd and pos.market_value_hkd:
            pos.unrealized_pnl_hkd = pos.market_value_hkd - pos.total_cost_hkd
            if pos.total_cost_hkd != 0:
                pos.unrealized_pnl_pct = (pos.unrealized_pnl_hkd / pos.total_cost_hkd * 100).quantize(Decimal("0.0001"))
        updated += 1

    await db.commit()
    return {
        "rates_refreshed": {k: str(v) for k, v in rates.items()},
        "positions_recalculated": updated,
    }


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db)):
    """Return last sync time per broker (based on most recent snapshot)."""
    from sqlalchemy import func
    result = await db.execute(
        select(
            Account.broker,
            func.max(PositionSnapshot.created_at).label("last_sync"),
        )
        .join(PositionSnapshot, PositionSnapshot.account_id == Account.id)
        .group_by(Account.broker)
    )
    rows = result.fetchall()
    return {row.broker.value: row.last_sync.isoformat() if row.last_sync else None for row in rows}


# ── IBKR helpers ──────────────────────────────────────────────────────────────

async def _upsert_position_from_ibkr(
    db, account_id: int, pos: dict, snapshot_date: date, summary: dict
) -> None:
    symbol = pos["symbol"]
    hint = ibkr_guess_type(pos["asset_category"], pos.get("name", ""))
    asset, _ = await _get_or_create_asset(db, symbol, pos.get("name"), pos["currency"], hint)

    if not await _compliance_gate(db, asset, symbol, summary):
        return

    price_hkd, _ = await convert_to_hkd(db, pos["mark_price"], pos["currency"])
    value_hkd, _ = await convert_to_hkd(db, pos["position_value"], pos["currency"])
    cost_hkd, _ = await convert_to_hkd(db, pos["cost_basis_price"], pos["currency"])

    existing = await db.scalar(
        select(Position).where(Position.account_id == account_id, Position.asset_id == asset.id)
    )
    cost_basis_money = pos.get("cost_basis_money")  # total cost in original currency
    total_cost_local = cost_basis_money if cost_basis_money else pos["quantity"] * pos["cost_basis_price"]
    total_cost_hkd_val, _ = await convert_to_hkd(db, total_cost_local, pos["currency"])

    if existing:
        existing.quantity = pos["quantity"]
        existing.avg_cost = pos["cost_basis_price"]
        existing.avg_cost_hkd = cost_hkd
        existing.last_price = pos["mark_price"]
        existing.last_price_hkd = price_hkd
        existing.market_value_hkd = value_hkd
        existing.market_value_local = pos["position_value"]
        existing.total_cost_local = total_cost_local
        existing.total_cost_hkd = total_cost_hkd_val
        summary["positions_updated"] += 1
    else:
        db.add(Position(
            account_id=account_id, asset_id=asset.id,
            quantity=pos["quantity"],
            avg_cost=pos["cost_basis_price"], cost_currency=pos["currency"],
            avg_cost_hkd=cost_hkd,
            total_cost_local=total_cost_local,
            total_cost_hkd=total_cost_hkd_val,
            market_value_local=pos["position_value"],
            last_price=pos["mark_price"], last_price_hkd=price_hkd,
            market_value_hkd=value_hkd,
        ))
        summary["positions_imported"] += 1

    await _upsert_snapshot(db, account_id, asset.id, snapshot_date,
                           pos["quantity"], price_hkd, value_hkd, "ibkr_flex_api")


async def _upsert_trade_from_ibkr(db, account_id: int, trade: dict, summary: dict) -> None:
    hint = ibkr_guess_type(trade["asset_category"], trade.get("name", ""))
    asset, _ = await _get_or_create_asset(db, trade["symbol"], trade.get("name"), trade["currency"], hint)

    if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
        return

    raw = RawTransaction(
        trade_date=trade["trade_date"],
        tx_type=trade["tx_type"],
        symbol=trade["symbol"],
        quantity=trade["quantity"],
        price=trade["price"],
        gross_amount=abs(trade["proceeds"]),
        fee=trade["commission"],
        currency=trade["currency"],
        notes="IBKR Flex sync",
        asset_type_hint=hint,
    )
    fingerprint = _tx_fingerprint(account_id, raw)

    existing = await db.scalar(select(Transaction).where(Transaction.fingerprint == fingerprint))
    if existing:
        summary["transactions_skipped_duplicate"] += 1
        return

    tx_type = TransactionTypeEnum.BUY if trade["tx_type"] == "buy" else TransactionTypeEnum.SELL
    price_hkd, fx_rate = await convert_to_hkd(db, trade["price"], trade["currency"], trade["trade_date"])
    gross_hkd, _ = await convert_to_hkd(db, abs(trade["proceeds"]), trade["currency"], trade["trade_date"])
    fee_hkd, _ = await convert_to_hkd(db, trade["commission"], trade["currency"], trade["trade_date"])
    net = abs(trade["proceeds"]) - trade["commission"]
    net_hkd, _ = await convert_to_hkd(db, net, trade["currency"], trade["trade_date"])

    db.add(Transaction(
        account_id=account_id, asset_id=asset.id,
        tx_type=tx_type, trade_date=trade["trade_date"],
        quantity=trade["quantity"], price=trade["price"],
        gross_amount=abs(trade["proceeds"]), fee=trade["commission"], net_amount=net,
        currency=trade["currency"], fx_rate_to_hkd=fx_rate,
        price_hkd=price_hkd, gross_amount_hkd=gross_hkd,
        fee_hkd=fee_hkd, net_amount_hkd=net_hkd,
        source_file="ibkr_flex_api", fingerprint=fingerprint,
    ))
    summary["transactions_imported"] += 1


# ── Futu helpers ──────────────────────────────────────────────────────────────

async def _upsert_position_from_futu(
    db, account_id: int, pos: dict, snapshot_date: date, summary: dict
) -> None:
    asset, _ = await _get_or_create_asset(
        db, pos["symbol"], pos.get("name"), pos["currency"], pos.get("asset_type_hint", "stock")
    )

    if not await _compliance_gate(db, asset, pos["symbol"], summary):
        return

    price_hkd, _ = await convert_to_hkd(db, pos["current_price"], pos["currency"])
    value_hkd, _ = await convert_to_hkd(db, pos["market_value"], pos["currency"])
    cost_hkd, _ = await convert_to_hkd(db, pos["cost_price"], pos["currency"])

    existing = await db.scalar(
        select(Position).where(Position.account_id == account_id, Position.asset_id == asset.id)
    )
    total_cost_local = pos["quantity"] * pos["cost_price"]
    total_cost_hkd_val, _ = await convert_to_hkd(db, total_cost_local, pos["currency"])

    if existing:
        existing.quantity = pos["quantity"]
        existing.avg_cost = pos["cost_price"]
        existing.avg_cost_hkd = cost_hkd
        existing.last_price = pos["current_price"]
        existing.last_price_hkd = price_hkd
        existing.market_value_local = pos["market_value"]
        existing.market_value_hkd = value_hkd
        existing.total_cost_local = total_cost_local
        existing.total_cost_hkd = total_cost_hkd_val
        existing.unrealized_pnl_hkd = pos.get("unrealized_pnl")
        summary["positions_updated"] += 1
    else:
        db.add(Position(
            account_id=account_id, asset_id=asset.id,
            quantity=pos["quantity"],
            avg_cost=pos["cost_price"], cost_currency=pos["currency"],
            avg_cost_hkd=cost_hkd,
            market_value_local=pos["market_value"],
            market_value_hkd=value_hkd,
            total_cost_local=total_cost_local,
            total_cost_hkd=total_cost_hkd_val,
            last_price=pos["current_price"], last_price_hkd=price_hkd,
        ))
        summary["positions_imported"] += 1

    await _upsert_snapshot(db, account_id, asset.id, snapshot_date,
                           pos["quantity"], price_hkd, value_hkd, "futu_opend_api")


async def _upsert_trade_from_futu(db, account_id: int, trade: dict, summary: dict) -> None:
    asset, _ = await _get_or_create_asset(
        db, trade["symbol"], trade.get("name"), trade["currency"], trade.get("asset_type_hint", "stock")
    )
    if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
        return

    raw = RawTransaction(
        trade_date=trade["trade_date"],
        tx_type=trade["tx_type"],
        symbol=trade["symbol"],
        quantity=trade["quantity"],
        price=trade["price"],
        gross_amount=trade["gross_amount"],
        fee=trade["fee"],
        currency=trade["currency"],
        notes="Futu OpenD sync",
    )
    fingerprint = _tx_fingerprint(account_id, raw)

    existing = await db.scalar(select(Transaction).where(Transaction.fingerprint == fingerprint))
    if existing:
        summary["transactions_skipped_duplicate"] += 1
        return

    tx_type = TransactionTypeEnum.BUY if trade["tx_type"] == "buy" else TransactionTypeEnum.SELL
    price_hkd, fx_rate = await convert_to_hkd(db, trade["price"], trade["currency"], trade["trade_date"])
    gross_hkd, _ = await convert_to_hkd(db, trade["gross_amount"], trade["currency"], trade["trade_date"])
    net = trade["gross_amount"] - trade["fee"]
    net_hkd, _ = await convert_to_hkd(db, net, trade["currency"], trade["trade_date"])

    db.add(Transaction(
        account_id=account_id, asset_id=asset.id,
        tx_type=tx_type, trade_date=trade["trade_date"],
        quantity=trade["quantity"], price=trade["price"],
        gross_amount=trade["gross_amount"], fee=trade["fee"], net_amount=net,
        currency=trade["currency"], fx_rate_to_hkd=fx_rate,
        price_hkd=price_hkd, gross_amount_hkd=gross_hkd,
        fee_hkd=Decimal("0"), net_amount_hkd=net_hkd,
        source_file="futu_opend_api", fingerprint=fingerprint,
    ))
    summary["transactions_imported"] += 1


# ── Binance helpers ───────────────────────────────────────────────────────────

async def _upsert_position_from_binance(
    db, account_id: int, pos: dict, snapshot_date: date, summary: dict
) -> None:
    asset, _ = await _get_or_create_asset(
        db, pos["symbol"], pos.get("name"), pos["currency"], pos.get("asset_type_hint", "crypto")
    )

    if not await _compliance_gate(db, asset, pos["symbol"], summary):
        return

    price_hkd, fx = await convert_to_hkd(db, pos["current_price"], pos["currency"])
    market_value_local = pos["market_value"]
    value_hkd, _ = await convert_to_hkd(db, market_value_local, pos["currency"])

    existing = await db.scalar(
        select(Position).where(Position.account_id == account_id, Position.asset_id == asset.id)
    )
    if existing:
        existing.quantity          = pos["quantity"]
        existing.last_price        = pos["current_price"]
        existing.last_price_hkd    = price_hkd
        existing.market_value_local = market_value_local
        existing.market_value_hkd  = value_hkd
        summary["positions_updated"] += 1
    else:
        db.add(Position(
            account_id=account_id, asset_id=asset.id,
            quantity=pos["quantity"],
            avg_cost=Decimal("0"), cost_currency=pos["currency"],
            last_price=pos["current_price"], last_price_hkd=price_hkd,
            market_value_local=market_value_local,
            market_value_hkd=value_hkd,
        ))
        summary["positions_imported"] += 1

    await _upsert_snapshot(db, account_id, asset.id, snapshot_date,
                           pos["quantity"], price_hkd, value_hkd, "binance_api")


async def _upsert_trade_from_binance(db, account_id: int, trade: dict, summary: dict) -> None:
    asset, _ = await _get_or_create_asset(
        db, trade["symbol"], trade.get("name"), trade["currency"], trade.get("asset_type_hint", "crypto")
    )
    if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
        return

    raw = RawTransaction(
        trade_date=trade["trade_date"],
        tx_type=trade["tx_type"],
        symbol=trade["symbol"],
        quantity=trade["quantity"],
        price=trade["price"],
        gross_amount=trade["gross_amount"],
        fee=trade["fee"],
        currency=trade["currency"],
        notes="Binance API sync",
    )
    fingerprint = _tx_fingerprint(account_id, raw)

    existing = await db.scalar(select(Transaction).where(Transaction.fingerprint == fingerprint))
    if existing:
        summary["transactions_skipped_duplicate"] += 1
        return

    tx_type = TransactionTypeEnum.BUY if trade["tx_type"] == "buy" else TransactionTypeEnum.SELL
    price_hkd, fx_rate = await convert_to_hkd(db, trade["price"], trade["currency"], trade["trade_date"])
    gross_hkd, _ = await convert_to_hkd(db, trade["gross_amount"], trade["currency"], trade["trade_date"])
    fee_hkd, _ = await convert_to_hkd(db, trade["fee"], trade["currency"], trade["trade_date"])
    net = trade["gross_amount"] - trade["fee"]
    net_hkd, _ = await convert_to_hkd(db, net, trade["currency"], trade["trade_date"])

    db.add(Transaction(
        account_id=account_id, asset_id=asset.id,
        tx_type=tx_type, trade_date=trade["trade_date"],
        quantity=trade["quantity"], price=trade["price"],
        gross_amount=trade["gross_amount"], fee=trade["fee"], net_amount=net,
        currency=trade["currency"], fx_rate_to_hkd=fx_rate,
        price_hkd=price_hkd, gross_amount_hkd=gross_hkd,
        fee_hkd=fee_hkd, net_amount_hkd=net_hkd,
        source_file="binance_api", fingerprint=fingerprint,
    ))
    summary["transactions_imported"] += 1


# ── Cash helper ───────────────────────────────────────────────────────────────

async def _upsert_cash(
    db, account_id: int, cash: dict, snapshot_date: date, summary: dict
) -> None:
    """Import a cash balance as a position."""
    currency = cash.get("currency", "")
    amount = cash.get("ending_cash", Decimal("0"))
    if not currency or amount == Decimal("0"):
        return

    symbol = f"{currency}.CASH"
    asset, _ = await _get_or_create_asset(db, symbol, f"{currency} Cash", currency, "cash")

    value_hkd, fx_rate = await convert_to_hkd(db, amount, currency)

    existing = await db.scalar(
        select(Position).where(Position.account_id == account_id, Position.asset_id == asset.id)
    )
    if existing:
        existing.quantity = amount
        existing.last_price_hkd = fx_rate
        existing.market_value_local = amount
        existing.market_value_hkd = value_hkd
        existing.total_cost_local = amount
        existing.total_cost_hkd = value_hkd
        summary["positions_updated"] += 1
    else:
        db.add(Position(
            account_id=account_id, asset_id=asset.id,
            quantity=amount, avg_cost=Decimal("1"),
            cost_currency=currency, avg_cost_hkd=fx_rate,
            market_value_local=amount,
            total_cost_local=amount,
            total_cost_hkd=value_hkd,
            last_price=Decimal("1"), last_price_hkd=fx_rate,
            market_value_hkd=value_hkd,
        ))
        summary["positions_imported"] += 1

    await _upsert_snapshot(db, account_id, asset.id, snapshot_date,
                           amount, fx_rate, value_hkd, "ibkr_flex")


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _compliance_gate(db, asset: Asset, symbol: str, summary: dict) -> bool:
    """Returns True if position should be imported, False if blocked."""
    # Track reported symbols so each appears only once in the summary
    seen: set[str] = summary.setdefault("_seen", set())
    first_time = symbol not in seen
    seen.add(symbol)

    if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
        if first_time:
            summary["blocked"].append({"symbol": symbol, "reason": asset.compliance_reason})
        return False
    if asset.compliance_status == ComplianceStatusEnum.LEGACY_HOLD:
        if first_time:
            summary["legacy_hold"].append({"symbol": symbol, "reason": asset.compliance_reason})
        return True  # Still import
    if asset.compliance_status == ComplianceStatusEnum.REVIEW_REQUIRED:
        existing = await db.scalar(
            select(ComplianceReview).where(
                ComplianceReview.asset_id == asset.id,
                ComplianceReview.status == ReviewStatusEnum.PENDING,
            )
        )
        if not existing:
            db.add(ComplianceReview(
                asset_id=asset.id, symbol=symbol.upper(),
                flag_reason=asset.compliance_reason or "Unclassified asset",
                detected_type=asset.asset_type.value,
            ))
        if first_time:
            summary["flagged_for_review"].append({"symbol": symbol, "reason": asset.compliance_reason})
        return False
    return True


async def _upsert_snapshot(
    db, account_id: int, asset_id: int, snapshot_date: date,
    quantity: Decimal, price_hkd: Decimal, value_hkd: Decimal, source: str
) -> None:
    existing = await db.scalar(
        select(PositionSnapshot).where(
            PositionSnapshot.snapshot_date == snapshot_date,
            PositionSnapshot.account_id == account_id,
            PositionSnapshot.asset_id == asset_id,
        )
    )
    if existing:
        existing.quantity = quantity
        existing.price_hkd = price_hkd
        existing.market_value_hkd = value_hkd
        existing.source_file = source
    else:
        db.add(PositionSnapshot(
            snapshot_date=snapshot_date, account_id=account_id, asset_id=asset_id,
            quantity=quantity, price_hkd=price_hkd, market_value_hkd=value_hkd,
            source_file=source,
        ))
